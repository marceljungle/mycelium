"""MuQ model integration for generating pure acoustic embeddings.

Uses the official ``muq`` package which provides the custom ``MuQ`` class.
``AutoModel`` cannot load this model because it defines a custom architecture
without a standard HuggingFace ``model_type``.
"""

import logging
from pathlib import Path
from typing import Any, List, Optional

import librosa
import numpy as np
import torch
from muq import MuQ

from ...domain.repositories import EmbeddingGenerator

logger = logging.getLogger(__name__)


class MuQEmbeddingGenerator(EmbeddingGenerator):
    """Implementation of EmbeddingGenerator using MuQ for acoustic embeddings.

    This generator does NOT support text search — only audio-based similarity.
    """

    @property
    def supports_text_search(self) -> bool:
        """MuQ does not support text embeddings."""
        return False

    def __init__(
            self,
            model_id: str = "OpenMuQ/MuQ-large-msd-iter",
            target_sr: int = 24000,
            chunk_duration_s: int = 30,
            micro_batch_size: int = 4,
    ):
        self.model_id = model_id
        self.target_sr = target_sr
        self.chunk_duration_s = chunk_duration_s
        self.micro_batch_size = micro_batch_size

        self.device = self.get_best_device()
        logger.info(f"MuQ selected device: {self.device}")

        # Lazy loading
        self.model: Optional[Any] = None

        # Determine optimal dtype: bfloat16 has the same dynamic range as
        # float32 (avoiding NaN that float16 causes) but uses half the memory.
        self.model_dtype = self._select_dtype()
        logger.info(f"MuQ inference dtype: {self.model_dtype}")

    def _select_dtype(self) -> torch.dtype:
        """Pick bfloat16 if the device supports it, otherwise float32.

        float16 is intentionally excluded — MuQ-Large produces NaN outputs
        with standard half-precision due to overflow in the attention layers.
        """
        if self.device == "cuda":
            if torch.cuda.is_bf16_supported():
                return torch.bfloat16
            return torch.float32

        if self.device == "mps":
            try:
                # MPS bfloat16 support was added in later PyTorch versions.
                t = torch.tensor([1.0], dtype=torch.bfloat16, device="mps")
                _ = t + t  # verify compute works, not just allocation
                return torch.bfloat16
            except (RuntimeError, TypeError):
                return torch.float32

        return torch.float32

    def _load_model_if_needed(self) -> None:
        """Loads the MuQ model on the first call that needs it."""
        if self.model is None:
            logger.info(
                f"Loading MuQ model '{self.model_id}' to device '{self.device}' "
                f"with dtype {self.model_dtype}..."
            )

            self.model = MuQ.from_pretrained(self.model_id)
            self.model.to(device=self.device, dtype=self.model_dtype)
            self.model.eval()

            logger.info("MuQ model loaded successfully.")
            try:
                param_dtype = next(self.model.parameters()).dtype
                logger.info(f"Model parameter dtype: {param_dtype}")
            except StopIteration:
                logger.debug("Could not determine model dtype (no parameters found).")

    @staticmethod
    def get_best_device() -> str:
        """Get the best available compute device."""
        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def can_use_half_precision(self) -> bool:
        """Whether the model is running in a reduced-precision mode."""
        return self.model_dtype != torch.float32

    def _get_model(self) -> Any:
        """Return a ready-to-use model."""
        self._load_model_if_needed()
        assert self.model is not None
        return self.model

    def _extract_chunks(self, filepath: Path) -> List[np.ndarray]:
        """Load audio and extract sequential non-overlapping windows."""
        chunk_size_samples = self.chunk_duration_s * self.target_sr

        waveform, _ = librosa.load(
            str(filepath),
            sr=self.target_sr,
            mono=True,
        )

        total_samples = len(waveform)
        num_windows = total_samples // chunk_size_samples

        if num_windows == 0:
            logger.warning(
                f"File {filepath} is too short ({total_samples / self.target_sr:.1f}s) "
                f"for even one window of {self.chunk_duration_s}s."
            )
            return []

        chunks = []
        for window_idx in range(num_windows):
            start_idx = window_idx * chunk_size_samples
            end_idx = start_idx + chunk_size_samples
            chunks.append(waveform[start_idx:end_idx])

        return chunks

    def generate_embedding(self, filepath: Path) -> Optional[List[float]]:
        """Generate embedding for a single audio file by delegating to batch method."""
        results = self.generate_embedding_batch([filepath])
        return results[0] if results else None

    def generate_embedding_batch(self, filepaths: List[Path]) -> List[Optional[List[float]]]:
        """Generate embeddings for multiple audio files using micro-batching.

        MuQ accepts raw waveform tensors of shape ``(batch, time)`` directly.
        To avoid OOM on unified-memory devices (Apple Silicon) and limited-VRAM
        GPUs, chunks are processed in small micro-batches and results are moved
        to CPU immediately after each forward pass.
        """
        if not filepaths:
            return []

        try:
            model = self._get_model()

            all_chunks: list[np.ndarray] = []
            file_chunk_counts: list[int] = []

            for filepath in filepaths:
                try:
                    chunks = self._extract_chunks(filepath)
                    if not chunks:
                        file_chunk_counts.append(0)
                        continue
                    all_chunks.extend(chunks)
                    file_chunk_counts.append(len(chunks))
                except Exception as e:
                    logger.error(f"Error loading audio file {filepath}: {e}")
                    file_chunk_counts.append(0)

            if not all_chunks:
                return [None] * len(filepaths)

            # Process chunks in micro-batches to prevent OOM / swap explosion.
            chunk_embeddings_list: list[torch.Tensor] = []
            micro_batch_size = self.micro_batch_size

            with torch.no_grad():
                for i in range(0, len(all_chunks), micro_batch_size):
                    batch_chunks = all_chunks[i:i + micro_batch_size]

                    waveform_batch = torch.tensor(
                        np.stack(batch_chunks), dtype=self.model_dtype
                    ).to(self.device)

                    outputs = model(waveform_batch)
                    pooled = outputs.last_hidden_state.mean(dim=1)

                    # Move to CPU immediately and cast to float32 for
                    # stable normalization downstream.
                    chunk_embeddings_list.append(pooled.cpu().float())

                    # Flush residual device memory.
                    if self.device == "mps":
                        torch.mps.empty_cache()
                    elif self.device == "cuda":
                        torch.cuda.empty_cache()

            # All tensors are on CPU now — concatenate and finish.
            chunk_embeddings = torch.cat(chunk_embeddings_list, dim=0)

            # Split results back to individual files and compute mean embeddings
            results: list[Optional[List[float]]] = []
            chunk_idx = 0

            for chunk_count in file_chunk_counts:
                if chunk_count == 0:
                    results.append(None)
                else:
                    file_features = chunk_embeddings[chunk_idx:chunk_idx + chunk_count]
                    mean_embedding = torch.mean(file_features, dim=0)
                    normalized_embedding = torch.nn.functional.normalize(
                        mean_embedding, p=2, dim=0
                    )
                    results.append(normalized_embedding.numpy().tolist())
                    chunk_idx += chunk_count

            logger.info(
                f"MuQ: processed batch of {len(filepaths)} audio files "
                f"({len(all_chunks)} total chunks, micro_batch_size={micro_batch_size})"
            )
            return results

        except Exception as e:
            logger.error(f"Error in MuQ batch audio embedding generation: {e}", exc_info=True)
            return [None] * len(filepaths)

    def unload_model(self) -> None:
        """Unload model to free GPU memory."""
        if self.model is not None:
            del self.model
            self.model = None

            if self.device == "cuda":
                torch.cuda.empty_cache()
            elif self.device == "mps":
                torch.mps.empty_cache()

            logger.info("MuQ model unloaded")

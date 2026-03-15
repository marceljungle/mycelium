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
    ):
        self.model_id = model_id
        self.target_sr = target_sr
        self.chunk_duration_s = chunk_duration_s

        self.device = self.get_best_device()
        logger.info(f"MuQ selected device: {self.device}")

        # Lazy loading
        self.model: Optional[Any] = None

        # MuQ must always run in FP32 — the authors explicitly warn that
        # FP16 inference causes NaN outputs.
        self.use_half = False
        logger.info("MuQ always uses full precision (FP32) to avoid NaN issues.")

    def _load_model_if_needed(self) -> None:
        """Loads the MuQ model on the first call that needs it."""
        if self.model is None:
            logger.info(f"Loading MuQ model '{self.model_id}' to device '{self.device}'...")

            self.model = MuQ.from_pretrained(self.model_id)
            self.model.to(self.device)
            self.model.eval()

            logger.info("MuQ model loaded successfully.")
            try:
                logger.info(f"Model dtype after load: {next(self.model.parameters()).dtype}")
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
        """Checks once if the device supports half precision."""
        if self.device == "cuda":
            return True
        if self.device == "mps":
            try:
                torch.tensor([1.0], dtype=torch.half).to(self.device)
                return True
            except RuntimeError:
                logger.warning("MPS device does not support half precision, falling back to FP32.")
                return False
        return False

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
        """Generate embeddings for multiple audio files in a single GPU batch.

        MuQ accepts raw waveform tensors of shape ``(batch, time)`` directly —
        no feature extractor is needed.
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

            # All chunks are the same length (chunk_duration_s * target_sr)
            # so we can stack them directly into a batch tensor.
            waveform_batch = torch.tensor(
                np.stack(all_chunks), dtype=torch.float32
            ).to(self.device)

            with torch.no_grad():
                outputs = model(waveform_batch)
                # Pool over the time dimension to get a single vector per chunk
                chunk_embeddings = outputs.last_hidden_state.mean(dim=1)

            # Split results back to individual files and compute mean embeddings
            results: list[Optional[List[float]]] = []
            chunk_idx = 0

            for chunk_count in file_chunk_counts:
                if chunk_count == 0:
                    results.append(None)
                else:
                    file_features = chunk_embeddings[chunk_idx:chunk_idx + chunk_count]
                    mean_embedding = torch.mean(file_features, dim=0)
                    normalized_embedding = torch.nn.functional.normalize(mean_embedding, p=2, dim=0)
                    results.append(normalized_embedding.cpu().numpy().tolist())
                    chunk_idx += chunk_count

            logger.info(
                f"MuQ: processed batch of {len(filepaths)} audio files ({len(all_chunks)} total chunks)"
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

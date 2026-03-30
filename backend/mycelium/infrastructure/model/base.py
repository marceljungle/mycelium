"""Shared base class for audio embedding generators.

Houses the batch-orchestration loop (chunking → micro-batching → aggregate →
normalise) so that concrete adapters only need to implement model-specific
loading and a single forward-pass method.
"""

import logging
from abc import abstractmethod
from pathlib import Path
from typing import Any, List, Optional

import librosa
import numpy as np
import torch

from ...domain.repositories import EmbeddingGenerator

logger = logging.getLogger(__name__)


class BaseAudioEmbeddingGenerator(EmbeddingGenerator):
    """Template for audio-embedding models.

    Subclasses must implement:
      * ``_load_model_if_needed()`` — download / initialise model & deps
      * ``_forward_chunks(chunks)`` — run a list of numpy waveforms through
        the model and return a ``(N, dim)`` float32 CPU tensor.
      * ``unload_model()`` — free GPU resources

    Subclasses may override:
      * ``_fp16_blacklisted`` — set to ``True`` if the model's internal
        layers break with float16 (e.g. MuQ's nnAudio).
    """

    _fp16_blacklisted: bool = False
    """Set to True in subclasses whose internal layers are incompatible with
    float16 (e.g. nnAudio producing mismatched intermediates)."""

    def __init__(
        self,
        model_id: str,
        target_sr: int,
        chunk_duration_s: int = 30,
        micro_batch_size: int = 4,
    ):
        self.model_id = model_id
        self.target_sr = target_sr
        self.chunk_duration_s = chunk_duration_s
        self.micro_batch_size = micro_batch_size

        self.device = self.get_best_device()
        logger.info(f"{self.__class__.__name__} selected device: {self.device}")

        self.model_dtype = self._select_dtype()
        self._dtype_smoke_tested = False
        logger.info(f"{self.__class__.__name__} inference dtype: {self.model_dtype}")

        # Per-file error reasons populated during the last batch call.
        # Keyed by index in the filepaths list.
        self.last_batch_errors: dict[int, str] = {}

    # ------------------------------------------------------------------
    # Device helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_best_device() -> str:
        """Get the best available compute device."""
        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _clear_device_cache(self) -> None:
        """Flush residual GPU/MPS memory."""
        if self.device == "cuda":
            torch.cuda.empty_cache()
        elif self.device == "mps":
            torch.mps.empty_cache()

    # ------------------------------------------------------------------
    # Dtype selection & smoke test
    # ------------------------------------------------------------------

    def _select_dtype(self) -> torch.dtype:
        """Pick the best dtype for the current device and model.

        Priority:
          * CUDA — bfloat16 (if hw supports) → float16 → float32
          * MPS  — float16 → float32
          * CPU  — float32

        Models that set ``_fp16_blacklisted = True`` skip the float16 step.
        A follow-up smoke test (see ``_smoke_test_dtype``) catches any
        runtime incompatibility and falls back to float32.
        """
        if self.device == "cuda":
            if torch.cuda.is_bf16_supported():
                return torch.bfloat16
            if not self._fp16_blacklisted:
                return torch.float16
            return torch.float32
        if self.device == "mps" and not self._fp16_blacklisted:
            return torch.float16
        return torch.float32

    def _smoke_test_dtype(self) -> None:
        """Run a tiny forward pass to verify the chosen dtype works end-to-end.

        Called once after the first ``_load_model_if_needed``.  If the dtype
        causes a RuntimeError (e.g. internal layer mismatch) the model is
        automatically reloaded in float32.
        """
        if self._dtype_smoke_tested or self.model_dtype == torch.float32:
            return
        self._dtype_smoke_tested = True
        try:
            dummy = [np.zeros(self.target_sr, dtype=np.float32)]
            self._forward_chunks(dummy)
            logger.info(
                f"Dtype smoke test passed — {self.model_dtype} is usable."
            )
        except RuntimeError as e:
            if "should be the same" in str(e) or "expected" in str(e).lower():
                logger.warning(
                    f"Dtype smoke test failed ({e}). "
                    f"{self.model_dtype} not compatible with this hardware."
                )
                self._reload_as_float32()
            else:
                raise

    def _reload_as_float32(self) -> None:
        """Discard the current model and reload in float32."""
        logger.warning("Falling back to float32 — reloading model...")
        self.unload_model()
        self.model_dtype = torch.float32
        self._load_model_if_needed()

    def can_use_half_precision(self) -> bool:
        """Whether the model is running in a reduced-precision mode."""
        return self.model_dtype != torch.float32

    # ------------------------------------------------------------------
    # Audio chunking
    # ------------------------------------------------------------------

    def _extract_chunks(self, filepath: Path) -> tuple[List[np.ndarray], float]:
        """Load audio and split into non-overlapping windows of ``chunk_duration_s``.

        Returns:
            Tuple of ``(chunks, duration_seconds)``.  ``chunks`` is empty
            when the file is shorter than one full window.
        """
        chunk_samples = self.chunk_duration_s * self.target_sr

        waveform, _ = librosa.load(str(filepath), sr=self.target_sr, mono=True)
        total = len(waveform)
        duration_s = total / self.target_sr
        num_windows = total // chunk_samples

        if num_windows == 0:
            logger.warning(
                f"File {filepath} too short ({duration_s:.1f}s) "
                f"for a {self.chunk_duration_s}s window."
            )
            return [], duration_s

        chunks = [
            waveform[i * chunk_samples : (i + 1) * chunk_samples]
            for i in range(num_windows)
        ]
        return chunks, duration_s

    # ------------------------------------------------------------------
    # Abstract — subclass must implement
    # ------------------------------------------------------------------

    @abstractmethod
    def _load_model_if_needed(self) -> None:
        """Lazily initialise the model on first use."""

    @abstractmethod
    def _forward_chunks(self, chunks: List[np.ndarray]) -> torch.Tensor:
        """Run one micro-batch of waveform chunks through the model.

        Args:
            chunks: list of numpy float32 arrays, each of length
                    ``chunk_duration_s * target_sr``.

        Returns:
            ``(len(chunks), embedding_dim)`` **float32 CPU** tensor.
        """

    # ------------------------------------------------------------------
    # Batch orchestration (shared by all models)
    # ------------------------------------------------------------------

    def generate_embedding(self, filepath: Path) -> Optional[List[float]]:
        """Generate embedding for a single audio file."""
        results = self.generate_embedding_batch([filepath])
        return results[0] if results else None

    def generate_embedding_batch(
        self, filepaths: List[Path]
    ) -> List[Optional[List[float]]]:
        """Generate embeddings for multiple audio files with micro-batching."""
        self.last_batch_errors = {}
        if not filepaths:
            return []

        try:
            self._load_model_if_needed()
            self._smoke_test_dtype()

            # Phase 1: collect all chunks across files
            all_chunks: list[np.ndarray] = []
            file_chunk_counts: list[int] = []

            for idx, filepath in enumerate(filepaths):
                try:
                    chunks, duration_s = self._extract_chunks(filepath)
                    if not chunks:
                        file_chunk_counts.append(0)
                        self.last_batch_errors[idx] = (
                            f"Audio too short ({duration_s:.1f}s) for "
                            f"{self.chunk_duration_s}s window"
                        )
                        continue
                    all_chunks.extend(chunks)
                    file_chunk_counts.append(len(chunks))
                except Exception as e:
                    logger.error(f"Error loading audio file {filepath}: {e}")
                    file_chunk_counts.append(0)
                    self.last_batch_errors[idx] = f"Failed to load audio: {e}"

            if not all_chunks:
                return [None] * len(filepaths)

            # Phase 2: micro-batched forward passes
            embeddings_list: list[torch.Tensor] = []

            for i in range(0, len(all_chunks), self.micro_batch_size):
                batch = all_chunks[i : i + self.micro_batch_size]
                embeddings_list.append(self._forward_chunks(batch))
                self._clear_device_cache()

            chunk_embeddings = torch.cat(embeddings_list, dim=0)

            # Phase 3: aggregate per file — mean + L2 normalise
            results: list[Optional[List[float]]] = []
            idx = 0
            for count in file_chunk_counts:
                if count == 0:
                    results.append(None)
                else:
                    mean = chunk_embeddings[idx : idx + count].mean(dim=0)
                    normed = torch.nn.functional.normalize(mean, p=2, dim=0)
                    results.append(normed.numpy().tolist())
                    idx += count

            logger.info(
                f"{self.__class__.__name__}: processed {len(filepaths)} files "
                f"({len(all_chunks)} chunks, micro_batch_size={self.micro_batch_size})"
            )
            return results

        except Exception as e:
            logger.error(
                f"Error in {self.__class__.__name__} batch embedding: {e}",
                exc_info=True,
            )
            return [None] * len(filepaths)

"""MuQ-MuLan model integration for generating audio + text embeddings.

Uses the official ``muq`` package which provides the custom ``MuQMuLan`` class.
MuQ-MuLan extends the MuQ architecture with a MuLan text tower, enabling
both audio-based and text-based music search.
"""

import logging
from typing import Any, List, Optional

import numpy as np
import torch
from muq import MuQMuLan

from .base import BaseAudioEmbeddingGenerator

logger = logging.getLogger(__name__)


class MuQMuLanEmbeddingGenerator(BaseAudioEmbeddingGenerator):
    """Implementation of EmbeddingGenerator using MuQ-MuLan for audio + text embeddings."""

    _fp16_blacklisted: bool = True
    """MuQ-MuLan's internal nnAudio layers produce float16 intermediates that
    conflict with bfloat16/float16 model weights on some hardware."""

    @property
    def supports_text_search(self) -> bool:
        """MuQ-MuLan supports both text and audio embeddings."""
        return True

    def __init__(
            self,
            model_id: str = "OpenMuQ/MuQ-MuLan-large",
            target_sr: int = 24000,
            chunk_duration_s: int = 10,
            micro_batch_size: int = 4,
    ):
        super().__init__(
            model_id=model_id,
            target_sr=target_sr,
            chunk_duration_s=chunk_duration_s,
            micro_batch_size=micro_batch_size,
        )

        # Lazy loading
        self.model: Optional[Any] = None

    # ------------------------------------------------------------------
    # Base-class hooks
    # ------------------------------------------------------------------

    def _load_model_if_needed(self) -> None:
        """Loads the MuQ-MuLan model on the first call that needs it."""
        if self.model is None:
            logger.info(
                f"Loading MuQ-MuLan model '{self.model_id}' to device "
                f"'{self.device}' with dtype {self.model_dtype}..."
            )

            self.model = MuQMuLan.from_pretrained(self.model_id)
            self.model.to(device=self.device, dtype=self.model_dtype)
            self.model.eval()

            logger.info("MuQ-MuLan model loaded successfully.")
            try:
                param_dtype = next(self.model.parameters()).dtype
                logger.info(f"Model parameter dtype: {param_dtype}")
            except StopIteration:
                logger.debug("Could not determine model dtype (no parameters found).")

    def _forward_chunks(self, chunks: List[np.ndarray]) -> torch.Tensor:
        """Run a micro-batch through MuQ-MuLan and return ``(N, dim)`` float32 CPU tensor."""
        self._load_model_if_needed()
        assert self.model is not None

        waveform_batch = torch.tensor(
            np.stack(chunks), dtype=self.model_dtype
        ).to(self.device)

        with torch.no_grad():
            # extract_audio_latents handles internal 10s clip splitting
            latents = self.model.extract_audio_latents(waveform_batch)

        return latents.cpu().float()

    def unload_model(self) -> None:
        """Unload model to free GPU memory."""
        if self.model is not None:
            del self.model
            self.model = None
            self._clear_device_cache()
            logger.info("MuQ-MuLan model unloaded")

    # ------------------------------------------------------------------
    # Text embedding methods (MuQ-MuLan specific)
    # ------------------------------------------------------------------

    def generate_text_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for a single text query by delegating to batch method."""
        results = self.generate_text_embedding_batch([text])
        return results[0] if results else None

    def generate_text_embedding_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Generate embeddings for multiple text queries in a single GPU batch."""
        if not texts:
            return []

        try:
            self._load_model_if_needed()
            assert self.model is not None

            with torch.no_grad():
                text_latents = self.model.extract_text_latents(texts)
                text_embeddings = torch.nn.functional.normalize(
                    text_latents, p=2, dim=-1
                )

            results = text_embeddings.cpu().float().numpy().tolist()
            logger.info(f"Successfully processed batch of {len(texts)} text queries")
            return results

        except Exception as e:
            logger.error(
                f"Error in batch text embedding generation: {e}", exc_info=True
            )
            return [None] * len(texts)

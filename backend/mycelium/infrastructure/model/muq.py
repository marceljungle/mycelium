"""MuQ model integration for generating pure acoustic embeddings.

Uses the official ``muq`` package which provides the custom ``MuQ`` class.
``AutoModel`` cannot load this model because it defines a custom architecture
without a standard HuggingFace ``model_type``.
"""

import logging
from typing import Any, List, Optional

import numpy as np
import torch
from muq import MuQ

from .base import BaseAudioEmbeddingGenerator

logger = logging.getLogger(__name__)


class MuQEmbeddingGenerator(BaseAudioEmbeddingGenerator):
    """Implementation of EmbeddingGenerator using MuQ for acoustic embeddings."""

    _fp16_blacklisted: bool = True
    """MuQ's internal nnAudio layers produce float16 intermediates that
    conflict with bfloat16/float16 model weights on some hardware."""

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

    def _forward_chunks(self, chunks: List[np.ndarray]) -> torch.Tensor:
        """Run a micro-batch through MuQ and return ``(N, dim)`` float32 CPU tensor."""
        self._load_model_if_needed()
        assert self.model is not None

        waveform_batch = torch.tensor(
            np.stack(chunks), dtype=self.model_dtype
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(waveform_batch)
            pooled = outputs.last_hidden_state.mean(dim=1)

        return pooled.cpu().float()

    def unload_model(self) -> None:
        """Unload model to free GPU memory."""
        if self.model is not None:
            del self.model
            self.model = None
            self._clear_device_cache()
            logger.info("MuQ model unloaded")

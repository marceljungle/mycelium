"""CLAP model integration for generating embeddings."""

import logging
from typing import List, Optional

import numpy as np
import torch
from transformers import ClapModel, ClapProcessor

from .base import BaseAudioEmbeddingGenerator

logger = logging.getLogger(__name__)


class CLAPEmbeddingGenerator(BaseAudioEmbeddingGenerator):
    """Implementation of EmbeddingGenerator using LAION's CLAP model."""

    @property
    def supports_text_search(self) -> bool:
        """CLAP supports both text and audio embeddings."""
        return True

    def __init__(
            self,
            model_id: str = "laion/larger_clap_music_and_speech",
            target_sr: int = 48000,
            chunk_duration_s: int = 30,
            micro_batch_size: int = 4,
    ):
        super().__init__(
            model_id=model_id,
            target_sr=target_sr,
            chunk_duration_s=chunk_duration_s,
            micro_batch_size=micro_batch_size,
        )

        # Lazy loading. Model is not loaded on instantiation.
        self.model: Optional[ClapModel] = None
        self.processor: Optional[ClapProcessor] = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_processor(self) -> ClapProcessor:
        """Return a ready-to-use processor with a non-optional type."""
        self._load_model_if_needed()
        assert self.processor is not None
        return self.processor

    def _get_model(self) -> ClapModel:
        """Return a ready-to-use model with a non-optional type."""
        self._load_model_if_needed()
        assert self.model is not None
        return self.model

    def _prepare_inputs(self, inputs: dict) -> dict:
        """Move inputs to the correct device and cast floating tensors to the model's dtype."""
        model = self._get_model()
        model_dtype = next(model.parameters()).dtype
        prepared = {}
        for k, v in inputs.items():
            if isinstance(v, torch.Tensor):
                if v.is_floating_point():
                    prepared[k] = v.to(device=self.device, dtype=model_dtype)
                else:
                    prepared[k] = v.to(device=self.device)
            else:
                prepared[k] = v
        return prepared

    # ------------------------------------------------------------------
    # Base-class hooks
    # ------------------------------------------------------------------

    def _load_model_if_needed(self) -> None:
        """Loads the model and processor on the first call that needs them."""
        if self.model is None or self.processor is None:
            logger.info(
                f"Loading CLAP model '{self.model_id}' to device "
                f"'{self.device}' with dtype {self.model_dtype}..."
            )

            self.model = ClapModel.from_pretrained(self.model_id)
            self.model.to(device=self.device, dtype=self.model_dtype)
            self.processor = ClapProcessor.from_pretrained(self.model_id)

            self.model.eval()
            logger.info("CLAP model loaded successfully.")
            try:
                logger.info(
                    f"Model dtype after load: {next(self.model.parameters()).dtype}"
                )
            except StopIteration:
                logger.debug("Could not determine model dtype (no parameters found).")

    def _forward_chunks(self, chunks: List[np.ndarray]) -> torch.Tensor:
        """Run a micro-batch through CLAP and return ``(N, dim)`` float32 CPU tensor."""
        processor = self._get_processor()
        model = self._get_model()

        inputs = processor(
            audios=chunks,
            sampling_rate=self.target_sr,
            return_tensors="pt",
            padding=True,
        )
        inputs = self._prepare_inputs(inputs)

        with torch.no_grad():
            audio_features = model.get_audio_features(**inputs)

        return audio_features.cpu().float()

    def unload_model(self) -> None:
        """Unload model to free GPU memory."""
        if self.model is not None:
            del self.model
            del self.processor
            self.model = None
            self.processor = None
            self._clear_device_cache()
            logger.info("CLAP model unloaded")

    # ------------------------------------------------------------------
    # Text embedding methods (CLAP-specific)
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
            processor = self._get_processor()
            model = self._get_model()

            inputs = processor(
                text=texts,
                return_tensors="pt",
                padding=True,
            )
            inputs = self._prepare_inputs(inputs)

            with torch.no_grad():
                text_features = model.get_text_features(**inputs)
                text_embeddings = torch.nn.functional.normalize(
                    text_features, p=2, dim=-1
                )

            results = text_embeddings.cpu().numpy().tolist()
            logger.info(f"Successfully processed batch of {len(texts)} text queries")
            return results

        except Exception as e:
            logger.error(
                f"Error in batch text embedding generation: {e}", exc_info=True
            )
            return [None] * len(texts)

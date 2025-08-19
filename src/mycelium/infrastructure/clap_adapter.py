"""CLAP model integration for generating embeddings."""

import logging
from pathlib import Path
from typing import List, Optional

import librosa
import torch
from transformers import ClapModel, ClapProcessor

from ..domain.repositories import EmbeddingGenerator


class CLAPEmbeddingGenerator(EmbeddingGenerator):
    """ Implementation of EmbeddingGenerator using LAION's CLAP model. """

    def __init__(
            self,
            model_id: str = "laion/larger_clap_music_and_speech",
            target_sr: int = 48000,
            chunk_duration_s: int = 10
    ):
        self.model_id = model_id
        self.target_sr = target_sr
        self.chunk_duration_s = chunk_duration_s
        self.logger = logging.getLogger(__name__)

        self.device = self._get_best_device()
        self.logger.info(f"Selected device: {self.device}")

        ## Lazy loading. Model is not loaded on instantiation.
        self._model: Optional[ClapModel] = None
        self._processor: Optional[ClapProcessor] = None

        self.use_half = self._can_use_half_precision()
        if self.use_half:
            self.logger.info("Half precision (FP16) is supported and will be used.")
        else:
            self.logger.info("Half precision not supported, using full precision (FP32).")

    def _load_model_if_needed(self):
        """Loads the model and processor on the first call that needs them."""
        if self._model is None or self._processor is None:
            self.logger.info(f"Loading model '{self.model_id}' to device '{self.device}'...")
            self._model = ClapModel.from_pretrained(self.model_id).to(self.device)
            self._processor = ClapProcessor.from_pretrained(self.model_id)

            ## Apply.half() to the model only if using half precision.
            if self.use_half:
                self._model.half()

            self._model.eval()
            self.logger.info("Model loaded successfully.")

    def _get_best_device(self) -> str:
        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _can_use_half_precision(self) -> bool:
        """Checks once if the device supports half precision."""
        if self.device == "cuda":
            # Most modern CUDA devices support FP16.
            return True
        if self.device == "mps":
            # Check for potential runtime errors on some MPS devices.
            try:
                torch.tensor([1.0], dtype=torch.half).to(self.device)
                return True
            except RuntimeError:
                self.logger.warning("MPS device does not support half precision, falling back to FP32.")
                return False
        return False

    def _get_processor(self) -> ClapProcessor:
        """Return a ready-to-use processor with a non-optional type."""
        self._load_model_if_needed()
        assert self._processor is not None
        return self._processor

    def _get_model(self) -> ClapModel:
        """Return a ready-to-use model with a non-optional type."""
        self._load_model_if_needed()
        assert self._model is not None
        return self._model

    def generate_embedding(self, filepath: Path) -> Optional[List[float]]:
        try:
            processor = self._get_processor()
            model = self._get_model()

            waveform, _ = librosa.load(str(filepath), sr=self.target_sr, mono=True)
            chunk_size = self.chunk_duration_s * self.target_sr
            chunks = [waveform[i:i + chunk_size] for i in range(0, len(waveform), chunk_size)]

            if len(chunks) > 1 and len(chunks[-1]) < self.target_sr:
                chunks.pop(-1)
            if not chunks:
                self.logger.warning(f"File {filepath} is too short to process.")
                return None

            inputs = processor(
                audios=chunks,
                sampling_rate=self.target_sr,
                return_tensors="pt",
                padding=True
            )

            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                audio_features = model.get_audio_features(**inputs)
                mean_embedding = torch.mean(audio_features, dim=0)
                normalized_embedding = torch.nn.functional.normalize(mean_embedding, p=2, dim=0)

            return normalized_embedding.cpu().numpy().tolist()

        except Exception as e:
            self.logger.error(f"Error generating audio embedding for {filepath}: {e}", exc_info=True)
            return None

    def generate_text_embedding(self, text: str) -> Optional[List[float]]:
        try:
            processor = self._get_processor()
            model = self._get_model()

            inputs = processor(
                text=[text],
                return_tensors="pt",
                padding=True
            )

            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                text_features = model.get_text_features(**inputs)
                text_embedding = torch.nn.functional.normalize(text_features, p=2, dim=-1)

            return text_embedding.cpu().numpy().tolist()

        except Exception as e:
            self.logger.error(f"Error generating text embedding for '{text}': {e}", exc_info=True)
            return None
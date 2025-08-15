"""CLAP model integration for generating embeddings."""

import logging
from pathlib import Path
from typing import List, Optional

import librosa
import torch
from transformers import ClapModel, ClapProcessor

from ..domain.repositories import EmbeddingGenerator


class CLAPEmbeddingGenerator(EmbeddingGenerator):
    """Implementation of EmbeddingGenerator using CLAP model."""
    
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
        
        # Setup device with MPS support for Apple Silicon
        self.device = self._get_best_device()
        self.logger.info(f"Using device: {self.device}")
        
        # Load model and processor
        self.model = ClapModel.from_pretrained(model_id).to(self.device)
        self.processor = ClapProcessor.from_pretrained(model_id)

        # Apply optimizations based on device
        if self.device == "cuda":
            self.model.half()
        elif self.device == "mps":
            try:
                self.model.half()
                torch.backends.mps.enabled = True
                self.logger.info("MPS half precision enabled for optimal performance")
            except RuntimeError as e:
                self.logger.warning(f"MPS half precision not supported, using FP32: {e}")
                # Fallback to FP32 if half precision fails

        self.model.eval()
    
    def _get_best_device(self) -> str:
        """Get the best available device for computation."""
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
        else:
            return "cpu"

    def _can_use_half_precision(self) -> bool:
        """Check if the current device supports half precision."""
        if self.device == "cuda":
            return True
        elif self.device == "mps":
            # Test if MPS supports half precision on this device
            try:
                test_tensor = torch.rand(1, device=self.device, dtype=torch.half)
                return True
            except RuntimeError:
                return False
        return False

    def generate_embedding(self, filepath: Path) -> Optional[List[float]]:
        try:
            waveform, sr = librosa.load(str(filepath), sr=self.target_sr, mono=True)

            chunk_len = self.chunk_duration_s * sr
            chunks = [waveform[i:i + chunk_len] for i in range(0, len(waveform), chunk_len)]

            if len(chunks) > 1 and len(chunks[-1]) < sr:
                chunks.pop(-1)
            if not chunks:
                return None

            inputs = self.processor(
                audios=chunks,
                sampling_rate=self.target_sr,
                return_tensors="pt",
                padding=True
            )

            use_half = self._can_use_half_precision()
            if use_half and self.device in ["cuda", "mps"]:
                inputs = {k: v.to(self.device).half() for k, v in inputs.items()}
            else:
                inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                audio_features = self.model.get_audio_features(**inputs)

                # Device-specific monitoring
                if self.device == "mps":
                    self.logger.debug(f"MPS memory used: {torch.mps.current_allocated_memory() / 1024 ** 2:.1f} MB")
                    self.logger.debug(f"Audio features device: {audio_features.device}")
                    self.logger.debug(f"Audio features dtype: {audio_features.dtype}")
                elif self.device == "cuda":
                    self.logger.debug(f"CUDA memory used: {torch.cuda.memory_allocated() / 1024 ** 2:.1f} MB")
                    self.logger.debug(f"Audio features device: {audio_features.device}")
                    self.logger.debug(f"Audio features dtype: {audio_features.dtype}")

                mean_embedding = torch.mean(audio_features, dim=0)
                normalized_embedding = torch.nn.functional.normalize(mean_embedding, p=2, dim=0)

            return normalized_embedding.cpu().numpy().tolist()

        except Exception as e:
            self.logger.error(f"Error generating embeddings for {filepath}: {e}", exc_info=True)
            return None
    
    def generate_text_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text description."""
        try:
            text_inputs = self.processor(
                text=[text], 
                return_tensors="pt", 
                padding=True
            )

            # Move to device first
            text_inputs = {k: v.to(self.device) for k, v in text_inputs.items()}

            # Apply half precision only to appropriate tensors (not token indices)
            use_half = self._can_use_half_precision()
            if use_half and (self.device == "cuda" or self.device == "mps"):
                # Only convert embeddings and attention masks to half precision
                # Keep input_ids as long tensors (they are token indices)
                for k, v in text_inputs.items():
                    if k not in ['input_ids']:  # Don't convert token indices to half
                        if v.dtype in [torch.float32, torch.float64]:
                            text_inputs[k] = v.half()

            with torch.no_grad():
                text_features = self.model.get_text_features(**text_inputs)
                text_embedding = torch.nn.functional.normalize(text_features, p=2, dim=-1)

            return text_embedding.cpu().numpy().tolist()[0]

        except Exception as e:
            self.logger.error(f"Error processing text '{text}': {e}", exc_info=True)
            return None
    
    def generate_embedding_from_file(self, filepath: Path) -> List[float]:
        """Alias for generate_embedding for consistency."""
        return self.generate_embedding(filepath)
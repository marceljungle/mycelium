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

        self.device = self.get_best_device()
        self.logger.info(f"Selected device: {self.device}")

        ## Lazy loading. Model is not loaded on instantiation.
        self.model: Optional[ClapModel] = None
        self.processor: Optional[ClapProcessor] = None

        self.use_half = self.can_use_half_precision()
        if self.use_half:
            self.logger.info("Half precision (FP16) is supported and will be used.")
        else:
            self.logger.info("Half precision not supported, using full precision (FP32).")

    def _load_model_if_needed(self):
        """Loads the model and processor on the first call that needs them."""
        if self.model is None or self.processor is None:
            self.logger.info(f"Loading model '{self.model_id}' to device '{self.device}'...")

            self.model = ClapModel.from_pretrained(self.model_id).to(self.device)
            self.processor = ClapProcessor.from_pretrained(self.model_id)

            if self.use_half and self.device == "cuda":
                self.logger.info("Applying half precision (FP16) to model for CUDA device.")
                self.model.half()
            elif self.use_half and self.device == "mps":
                self.logger.warning(
                    "Half precision is supported but disabled on MPS device to prevent potential crashes. Using FP32.")

            self.model.eval()
            self.logger.info("Model loaded successfully.")
            try:
                self.logger.info(f"Model dtype after load: {next(self.model.parameters()).dtype}")
            except StopIteration:
                self.logger.debug("Could not determine model dtype (no parameters found).")

    @staticmethod
    def get_best_device() -> str:
        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def can_use_half_precision(self) -> bool:
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
        assert self.processor is not None
        return self.processor

    def _get_model(self) -> ClapModel:
        """Return a ready-to-use model with a non-optional type."""
        self._load_model_if_needed()
        assert self.model is not None
        return self.model

    def _prepare_inputs(self, inputs: dict) -> dict:
        """Move inputs to the correct device and cast floating tensors to the model's dtype.

        This prevents dtype mismatches when the model runs in half precision on CUDA.
        """
        model = self._get_model()
        # Determine model parameter dtype (e.g., torch.float32 or torch.float16)
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

            inputs = self._prepare_inputs(inputs)

            with torch.no_grad():
                audio_features = model.get_audio_features(**inputs)
                mean_embedding = torch.mean(audio_features, dim=0)
                normalized_embedding = torch.nn.functional.normalize(mean_embedding, p=2, dim=0)

            return normalized_embedding.cpu().numpy().tolist()

        except Exception as e:
            self.logger.error(f"Error generating audio embedding for {filepath}: {e}", exc_info=True)
            return None

    def generate_embedding_batch(self, filepaths: List[Path]) -> List[Optional[List[float]]]:
        """Generate embeddings for multiple audio files in a single GPU batch"""
        if not filepaths:
            return []
        
        try:
            processor = self._get_processor()
            model = self._get_model()
            
            all_chunks = []
            file_chunk_counts = []
            loaded_waveforms = []  # Keep track for cleanup
            
            # Load and prepare all audio files
            for filepath in filepaths:
                try:
                    waveform, _ = librosa.load(
                        str(filepath), 
                        sr=self.target_sr, 
                        mono=True,
                        duration=120
                    )
                    loaded_waveforms.append(waveform)  # Keep reference for cleanup
                    
                    chunk_size = self.chunk_duration_s * self.target_sr
                    chunks = [waveform[i:i + chunk_size] for i in range(0, len(waveform), chunk_size)]
                    
                    if len(chunks) > 1 and len(chunks[-1]) < self.target_sr:
                        chunks.pop(-1)
                    
                    if not chunks:
                        self.logger.warning(f"File {filepath} is too short to process.")
                        file_chunk_counts.append(0)
                        continue
                    
                    all_chunks.extend(chunks)
                    file_chunk_counts.append(len(chunks))
                    
                except Exception as e:
                    self.logger.error(f"Error loading audio file {filepath}: {e}")
                    file_chunk_counts.append(0)
                    loaded_waveforms.append(None)  # Maintain list alignment
            
            try:
                if not all_chunks:
                    return [None] * len(filepaths)
                
                # Process all chunks in a single batch with memory management
                inputs = processor(
                    audios=all_chunks,
                    sampling_rate=self.target_sr,
                    return_tensors="pt",
                    padding=True
                )
                
                inputs = self._prepare_inputs(inputs)
                
                with torch.no_grad():
                    audio_features = model.get_audio_features(**inputs)
                
                # Clear input tensors from memory immediately
                del inputs
                if self.device == "cuda":
                    torch.cuda.empty_cache()
                elif self.device == "mps":
                    torch.mps.empty_cache()
                
                # Split results back to individual files and compute mean embeddings
                results = []
                chunk_idx = 0
                
                for chunk_count in file_chunk_counts:
                    if chunk_count == 0:
                        results.append(None)
                    else:
                        file_features = audio_features[chunk_idx:chunk_idx + chunk_count]
                        mean_embedding = torch.mean(file_features, dim=0)
                        normalized_embedding = torch.nn.functional.normalize(mean_embedding, p=2, dim=0)
                        results.append(normalized_embedding.cpu().numpy().tolist())
                        chunk_idx += chunk_count
                
                self.logger.info(f"Successfully processed batch of {len(filepaths)} audio files ({len(all_chunks)} total chunks)")
                return results
                
            finally:
                # Aggressive cleanup
                del loaded_waveforms
                del all_chunks
                if 'audio_features' in locals():
                    del audio_features
                
                # Force garbage collection
                import gc
                collected = gc.collect()
                if collected > 0:
                    self.logger.debug(f"Audio batch cleanup: collected {collected} objects")
                
                # Clear GPU cache
                if self.device == "cuda":
                    torch.cuda.empty_cache()
                elif self.device == "mps":
                    torch.mps.empty_cache()
            
        except Exception as e:
            self.logger.error(f"Error in batch audio embedding generation: {e}", exc_info=True)
            # Fall back to individual processing
            return [self.generate_embedding(fp) for fp in filepaths]

    def generate_text_embedding(self, text: str) -> Optional[List[float]]:
        try:
            processor = self._get_processor()
            model = self._get_model()

            inputs = processor(
                text=[text],
                return_tensors="pt",
                padding=True
            )

            inputs = self._prepare_inputs(inputs)

            with torch.no_grad():
                text_features = model.get_text_features(**inputs)
                text_embedding = torch.nn.functional.normalize(text_features, p=2, dim=-1)

            return text_embedding.cpu().numpy().tolist()[0]

        except Exception as e:
            self.logger.error(f"Error generating text embedding for '{text}': {e}", exc_info=True)
            return None

    def generate_text_embedding_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Generate embeddings for multiple text queries in a single GPU batch for better utilization."""
        if not texts:
            return []
        
        try:
            processor = self._get_processor()
            model = self._get_model()
            
            inputs = processor(
                text=texts,
                return_tensors="pt",
                padding=True
            )
            
            inputs = self._prepare_inputs(inputs)
            
            with torch.no_grad():
                text_features = model.get_text_features(**inputs)
                text_embeddings = torch.nn.functional.normalize(text_features, p=2, dim=-1)
            
            # Convert to list of lists
            results = text_embeddings.cpu().numpy().tolist()
            self.logger.info(f"Successfully processed batch of {len(texts)} text queries")
            return results
            
        except Exception as e:
            self.logger.error(f"Error in batch text embedding generation: {e}", exc_info=True)
            # Fall back to individual processing
            return [self.generate_text_embedding(text) for text in texts]

    def unload_model(self) -> None:
        """Unload model to free GPU memory."""
        if self.model is not None:
            del self.model
            del self.processor
            self.model = None
            self.processor = None

            if self.device == "cuda":
                torch.cuda.empty_cache()
            elif self.device == "mps":
                torch.mps.empty_cache()

            self.logger.info("Model unloaded")
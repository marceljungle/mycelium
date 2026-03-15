"""MuQ model integration for generating pure acoustic embeddings."""

import logging
from pathlib import Path
from typing import List, Optional

import librosa
import torch
from transformers import AutoModel, AutoFeatureExtractor

from ...domain.repositories import EmbeddingGenerator

logger = logging.getLogger(__name__)


class MuQEmbeddingGenerator(EmbeddingGenerator):
    """Implementation of EmbeddingGenerator using MuQ-large for acoustic embeddings.
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
        self.model: Optional[AutoModel] = None
        self.feature_extractor: Optional[AutoFeatureExtractor] = None

        # MuQ must always run in FP32 — the authors explicitly warn that
        # FP16 inference causes NaN outputs.
        self.use_half = False
        logger.info("MuQ always uses full precision (FP32) to avoid NaN issues.")

    def _load_model_if_needed(self) -> None:
        """Loads the model and feature extractor on the first call that needs them."""
        if self.model is None or self.feature_extractor is None:
            logger.info(f"Loading MuQ model '{self.model_id}' to device '{self.device}'...")

            self.model = AutoModel.from_pretrained(
                self.model_id, trust_remote_code=True
            ).to(self.device)
            self.feature_extractor = AutoFeatureExtractor.from_pretrained(self.model_id)

            if self.use_half and self.device == "cuda":
                logger.info("Applying half precision (FP16) to model for CUDA device.")
                self.model.half()
            elif self.use_half and self.device == "mps":
                logger.warning(
                    "Half precision supported but disabled on MPS to prevent potential crashes. Using FP32."
                )

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

    def _get_model(self) -> AutoModel:
        """Return a ready-to-use model with a non-optional type."""
        self._load_model_if_needed()
        assert self.model is not None
        return self.model

    def _get_feature_extractor(self) -> AutoFeatureExtractor:
        """Return a ready-to-use feature extractor with a non-optional type."""
        self._load_model_if_needed()
        assert self.feature_extractor is not None
        return self.feature_extractor

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

    def _extract_chunks(self, filepath: Path) -> List:
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
        """Generate embeddings for multiple audio files in a single GPU batch."""
        if not filepaths:
            return []

        try:
            feature_extractor = self._get_feature_extractor()
            model = self._get_model()

            all_chunks = []
            file_chunk_counts = []

            # Load and prepare all audio files
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

            # Process all chunks through the feature extractor
            inputs = feature_extractor(
                all_chunks,
                sampling_rate=self.target_sr,
                return_tensors="pt",
                padding=True
            )

            inputs = self._prepare_inputs(inputs)

            with torch.no_grad():
                outputs = model(**inputs)
                # Pool over the time dimension to get a single vector per chunk
                chunk_embeddings = outputs.last_hidden_state.mean(dim=1)

            # Split results back to individual files and compute mean embeddings
            results = []
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
            del self.feature_extractor
            self.model = None
            self.feature_extractor = None

            if self.device == "cuda":
                torch.cuda.empty_cache()
            elif self.device == "mps":
                torch.mps.empty_cache()

            logger.info("MuQ model unloaded")

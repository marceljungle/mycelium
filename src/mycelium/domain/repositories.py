"""Repository interfaces for domain layer."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from .models import Track, TrackEmbedding, SearchResult


class PlexRepository(ABC):
    """Interface for Plex data access."""
    
    @abstractmethod
    def get_all_tracks(self) -> List[Track]:
        """Get all tracks from the Plex music library."""
        pass


class EmbeddingRepository(ABC):
    """Interface for managing track embeddings."""
    
    @abstractmethod
    def save_embeddings(self, embeddings: List[TrackEmbedding]) -> None:
        """Save track embeddings to storage."""
        pass

    @abstractmethod
    def save_embedding(self, track_embedding: TrackEmbedding) -> None:
        """Save track embeddings to storage."""
        pass
    
    @abstractmethod
    def search_by_embedding(self, embedding: List[float], n_results: int = 10) -> List[SearchResult]:
        """Search for similar tracks by embedding."""
        pass
    
    @abstractmethod
    def get_embedding_count(self) -> int:
        """Get the total number of embeddings stored."""
        pass

    @abstractmethod
    def get_embedding_by_track_id(self, track_id: str) -> Optional[List[float]]:
        """Get embedding for a specific track by its ID."""
        pass

    @abstractmethod
    def has_embedding(self, track_id: str) -> Optional[List[float]]:
        """Get embedding for a specific track by its ID."""
        pass


class EmbeddingGenerator(ABC):
    """Interface for generating embeddings from audio files."""
    
    @abstractmethod
    def generate_embedding(self, filepath: Path) -> Optional[List[float]]:
        """Generate embedding for an audio file."""
        pass
    
    @abstractmethod
    def generate_text_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text description."""
        pass

    @staticmethod
    def get_best_device() -> str:
        """Get the best device for running the embedding model (e.g., 'cpu', 'cuda')."""
        pass

    @staticmethod
    def can_use_half_precision() -> bool:
        """Checks once if the device supports half precision."""
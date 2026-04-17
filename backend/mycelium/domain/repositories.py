"""Repository interfaces for domain layer."""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Track, TrackEmbedding, SearchResult, Playlist


class MediaServerRepository(ABC):
    """Interface for media server operations (Plex, Jellyfin, etc.)."""
    
    @abstractmethod
    def get_all_tracks(self) -> List[Track]:
        """Get all tracks from the music library."""
        ...
    
    @abstractmethod
    def get_track_by_id(self, track_id: str) -> Optional[Track]:
        """Get a specific track by its ID."""
        ...
    
    @abstractmethod
    def create_playlist(self, playlist: Playlist, batch_size: int = 100) -> Playlist:
        """Create a playlist on the media server."""
        ...
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
    def has_embedding(self, track_id: str) -> bool:
        """Check if an embedding exists for a specific track."""
        pass


class EmbeddingGenerator(ABC):
    """Interface for generating embeddings from audio files.
    
    Implementations must support audio embedding generation. Text embedding
    generation is optional — check `supports_text_search` before calling
    text methods.
    """
    
    @property
    def supports_text_search(self) -> bool:
        """Whether this generator supports text-to-embedding conversion.
        
        Models like CLAP support both text and audio embeddings.
        Models like MuQ only support audio embeddings.
        """
        return False

    @abstractmethod
    def generate_embedding(self, filepath: Path) -> Optional[List[float]]:
        """Generate embedding for an audio file."""
        pass
    
    @abstractmethod
    def generate_embedding_batch(self, filepaths: List[Path]) -> List[Optional[List[float]]]:
        """Generate embeddings for multiple audio files in a batch."""
        pass
    
    def generate_text_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text description.
        
        Only available when `supports_text_search` is True.
        
        Raises:
            NotImplementedError: If the model does not support text embeddings.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support text embeddings"
        )

    def generate_text_embedding_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Generate embeddings for multiple text queries in a batch.
        
        Only available when `supports_text_search` is True.
        
        Raises:
            NotImplementedError: If the model does not support text embeddings.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support text embeddings"
        )

    @abstractmethod
    def unload_model(self) -> None:
        """Unload model to free GPU memory."""
        pass

    @staticmethod
    def get_best_device() -> str:
        """Get the best device for running the embedding model (e.g., 'cpu', 'cuda')."""
        pass

    @staticmethod
    def can_use_half_precision() -> bool:
        """Checks once if the device supports half precision."""


class TrackRepository(ABC):
    """Interface for persisting and querying track metadata.

    Implementations provide the storage backend (SQLite, PostgreSQL, etc.)
    while the domain and application layers depend only on this interface.
    """

    @abstractmethod
    def save_tracks(
        self, tracks: List[Track], scan_timestamp: Optional[datetime] = None
    ) -> Dict[str, int]:
        """Persist tracks and return statistics (new / updated / total)."""
        ...

    @abstractmethod
    def get_track_by_id(self, media_server_rating_key: str) -> Optional[Track]:
        """Retrieve a single track by its media-server key."""
        ...

    @abstractmethod
    def get_all_tracks(
        self, limit: Optional[int] = None, offset: int = 0
    ) -> List[Track]:
        """List tracks with optional pagination."""
        ...

    @abstractmethod
    def search_tracks(
        self, search_query: str, limit: Optional[int] = None, offset: int = 0
    ) -> List[Track]:
        """Full-text search across artist / album / title."""
        ...

    @abstractmethod
    def count_search_tracks(self, search_query: str) -> int:
        """Count tracks matching a simple search query."""
        ...

    @abstractmethod
    def search_tracks_advanced(
        self,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        title: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Track]:
        """Search with per-field filters (AND logic)."""
        ...

    @abstractmethod
    def count_search_tracks_advanced(
        self,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        title: Optional[str] = None,
    ) -> int:
        """Count tracks matching advanced criteria."""
        ...

    @abstractmethod
    def get_unprocessed_tracks(
        self, model_id: str, limit: Optional[int] = None, skip_errored: bool = True
    ) -> List[Any]:
        """Return tracks not yet processed by *model_id*.

        When *skip_errored* is True (the default), tracks previously flagged
        as errored for this model are excluded from the results.
        """
        ...

    @abstractmethod
    def mark_track_processed(
        self, media_server_rating_key: str, model_id: str
    ) -> None:
        """Record that *model_id* has processed a track."""
        ...

    @abstractmethod
    def mark_track_errored(
        self,
        media_server_rating_key: str,
        model_id: str,
        error_category: str,
        error_message: str,
    ) -> None:
        """Flag a track as errored for *model_id*."""
        ...

    @abstractmethod
    def clear_track_error(
        self, media_server_rating_key: str, model_id: str
    ) -> None:
        """Remove the error flag for a track after a successful retry."""
        ...

    @abstractmethod
    def get_errored_track_count(self, model_id: str) -> int:
        """Return the number of errored tracks for *model_id*."""
        ...

    @abstractmethod
    def get_processing_stats(
        self, model_id: Optional[str] = None
    ) -> Dict[str, int]:
        """Return processing statistics keyed by {total,processed,unprocessed}_tracks."""
        ...

    @abstractmethod
    def get_track_count(self) -> int:
        """Return total number of stored tracks."""
        ...
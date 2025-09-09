"""Domain models for the Mycelium application."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional
from datetime import datetime


class MediaServerType(Enum):
    """Supported media server types."""
    PLEX = "plex"
    JELLYFIN = "jellyfin"


@dataclass
class Track:
    """Represents a music track from a media server."""

    media_server_rating_key: str
    media_server_type: MediaServerType
    artist: str = ""
    album: str = ""
    title: str = ""
    filepath: Optional[Path] = None

    @property
    def display_name(self) -> str:
        """Get a display-friendly name for the track."""
        return f"{self.artist} - {self.title}"
    
    @property
    def unique_id(self) -> str:
        """Get a unique identifier for the track across media servers."""
        return f"{self.media_server_type.value}:{self.media_server_rating_key}"
    



@dataclass
class TrackEmbedding:
    """Represents a track with its embedding from a specific model."""

    track: Track
    embedding: List[float]
    model_id: str
    processed_at: Optional[datetime] = None


@dataclass
class SearchResult:
    """Represents a search result with similarity score."""

    track: Track
    similarity_score: float
    distance: float


@dataclass
class Playlist:
    """Represents a playlist created from recommendations."""
    
    name: str
    tracks: List[Track]
    created_at: Optional[datetime] = None
    server_id: Optional[str] = None
    
    @property
    def track_count(self) -> int:
        """Get the number of tracks in the playlist."""
        return len(self.tracks)

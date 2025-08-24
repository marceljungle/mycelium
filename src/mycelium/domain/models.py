"""Domain models for the Mycelium application."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from datetime import datetime


@dataclass
class Track:
    """Represents a music track from Plex."""

    artist: str
    album: str
    title: str
    filepath: Path
    plex_rating_key: str

    @property
    def display_name(self) -> str:
        """Get a display-friendly name for the track."""
        return f"{self.artist} - {self.title}"


@dataclass
class TrackEmbedding:
    """Represents a track with its CLAP embedding."""

    track: Track
    embedding: List[float]


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

"""Domain models for the Mycelium application."""

from dataclasses import dataclass
from pathlib import Path
from typing import List


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

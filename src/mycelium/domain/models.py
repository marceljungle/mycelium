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
    
    @classmethod
    def from_dict(cls, data: dict) -> "TrackEmbedding":
        """Create TrackEmbedding from dictionary data."""
        track = Track(
            artist=data["artist"],
            album=data["album"],
            title=data["track_title"],
            filepath=Path(data["filepath"]),
            plex_rating_key=data["plex_rating_key"]
        )
        return cls(track=track, embedding=data["embedding"])
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "artist": self.track.artist,
            "album": self.track.album,
            "track_title": self.track.title,
            "filepath": str(self.track.filepath),
            "plex_rating_key": self.track.plex_rating_key,
            "embedding": self.embedding
        }


@dataclass
class SearchResult:
    """Represents a search result with similarity score."""
    
    track: Track
    similarity_score: float
    distance: float
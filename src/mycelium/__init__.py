"""Mycelium - Plex Music Recommendation System using CLAP embeddings."""

from .application import MyceliumService
from .config import MyceliumConfig
from .domain import Track, TrackEmbedding, SearchResult

__version__ = "0.1.0"
__author__ = "Marcel Jungle"
__email__ = "marcel@example.com"

__all__ = [
    "MyceliumService",
    "MyceliumConfig", 
    "Track",
    "TrackEmbedding",
    "SearchResult",
]
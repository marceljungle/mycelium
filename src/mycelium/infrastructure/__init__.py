"""Infrastructure package initialization."""

from .plex_adapter import PlexMusicRepository
from .clap_adapter import CLAPEmbeddingGenerator
from .chroma_adapter import ChromaEmbeddingRepository

__all__ = [
    "PlexMusicRepository",
    "CLAPEmbeddingGenerator",
    "ChromaEmbeddingRepository"
]

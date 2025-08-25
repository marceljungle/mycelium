"""Infrastructure package initialization."""

# Import database first as it has no external dependencies
from .track_database import TrackDatabase, StoredTrack, TrackEmbeddingRecord

__all__ = [
    "TrackDatabase",
    "StoredTrack",
    "TrackEmbeddingRecord"
]

# Try to import other components that have external dependencies
try:
    from .plex_adapter import PlexMusicRepository
    __all__.append("PlexMusicRepository")
except ImportError:
    pass

try:
    from .clap_adapter import CLAPEmbeddingGenerator
    __all__.append("CLAPEmbeddingGenerator")
except ImportError:
    pass

try:
    from .chroma_adapter import ChromaEmbeddingRepository
    __all__.append("ChromaEmbeddingRepository")
except ImportError:
    pass

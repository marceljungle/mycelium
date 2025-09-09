"""Infrastructure package initialization."""

# Import database first as it has no external dependencies
from .track_database import TrackDatabase, StoredTrack, TrackEmbeddingRecord

__all__ = [
    "TrackDatabase",
    "StoredTrack", 
    "TrackEmbeddingRecord"
]

# Note: Other components (PlexMusicRepository, CLAPEmbeddingGenerator, ChromaEmbeddingRepository)
# are imported lazily when needed to avoid loading heavy ML dependencies during CLI startup.
# They can be imported directly from their modules when required:
# - from mycelium.infrastructure.plex_adapter import PlexMusicRepository  
# - from mycelium.infrastructure.clap_adapter import CLAPEmbeddingGenerator
# - from mycelium.infrastructure.chroma_adapter import ChromaEmbeddingRepository

"""Configuration management for Mycelium."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class PlexConfig:
    """Configuration for Plex connection."""
    url: str = "http://localhost:32400"
    token: Optional[str] = None
    music_library_name: str = "Music"
    
    @classmethod
    def from_env(cls) -> "PlexConfig":
        """Create PlexConfig from environment variables."""
        return cls(
            url=os.environ.get("PLEX_URL", "http://localhost:32400"),
            token=os.environ.get("PLEX_TOKEN"),
            music_library_name=os.environ.get("PLEX_MUSIC_LIBRARY", "Music")
        )


@dataclass
class CLAPConfig:
    """Configuration for CLAP model."""
    model_id: str = "laion/larger_clap_music_and_speech"
    target_sr: int = 48000
    chunk_duration_s: int = 10
    batch_size: int = 16


@dataclass
class ChromaConfig:
    """Configuration for ChromaDB."""
    db_path: str = "./music_vector_db"
    collection_name: str = "my_music_library"
    batch_size: int = 1000


@dataclass
class APIConfig:
    """Configuration for API server."""
    host: str = "localhost"
    port: int = 8000
    reload: bool = False
    
    @classmethod
    def from_env(cls) -> "APIConfig":
        """Create APIConfig from environment variables."""
        return cls(
            host=os.environ.get("API_HOST", "localhost"),
            port=int(os.environ.get("API_PORT", "8000")),
            reload=os.environ.get("API_RELOAD", "false").lower() == "true"
        )


@dataclass
class MyceliumConfig:
    """Main configuration class."""
    plex: PlexConfig
    clap: CLAPConfig
    chroma: ChromaConfig
    api: APIConfig
    
    @classmethod
    def from_env(cls) -> "MyceliumConfig":
        """Create configuration from environment variables."""
        return cls(
            plex=PlexConfig.from_env(),
            clap=CLAPConfig(),
            chroma=ChromaConfig(),
            api=APIConfig.from_env()
        )
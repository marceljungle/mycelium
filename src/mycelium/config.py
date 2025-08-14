"""Configuration management for Mycelium."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Import new YAML configuration
from .config_yaml import MyceliumConfig, get_config_file_path


# Load environment variables from .env file for backward compatibility
def load_env_file():
    """Load environment variables from .env file if it exists."""
    # Look for .env file in the project root (going up from src/mycelium/)
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # Fallback: try to load from current directory
        load_dotenv()

# Load the .env file when this module is imported
load_env_file()


# Legacy classes for backward compatibility
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

    @classmethod
    def from_env(cls) -> "CLAPConfig":
        """Create CLAPConfig from environment variables."""
        return cls(
            model_id=os.environ.get("CLAP_MODEL_ID", "laion/larger_clap_music_and_speech"),
            target_sr=int(os.environ.get("CLAP_TARGET_SR", "48000")),
            chunk_duration_s=int(os.environ.get("CLAP_CHUNK_DURATION", "10")),
            batch_size=int(os.environ.get("CLAP_BATCH_SIZE", "16"))
        )


@dataclass
class ChromaConfig:
    """Configuration for ChromaDB."""
    db_path: str = "./music_vector_db"
    collection_name: str = "my_music_library"
    batch_size: int = 1000

    @classmethod
    def from_env(cls) -> "ChromaConfig":
        """Create ChromaConfig from environment variables."""
        return cls(
            db_path=os.environ.get("CHROMA_DB_PATH", "./music_vector_db"),
            collection_name=os.environ.get("COLLECTION_NAME", "my_music_library"),
            batch_size=int(os.environ.get("CHROMA_BATCH_SIZE", "1000"))
        )


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


# Export the new YAML-based configuration as the main one
__all__ = [
    "MyceliumConfig", 
    "get_config_file_path",
    "PlexConfig", 
    "CLAPConfig", 
    "ChromaConfig", 
    "APIConfig"
]
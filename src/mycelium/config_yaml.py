"""YAML-based configuration management for Mycelium."""

import os
import yaml
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, Any


def get_config_dir() -> Path:
    """Get the configuration directory for Mycelium."""
    home_dir = os.getenv('APPDATA') if os.name == 'nt' else os.path.expanduser('~/.config')
    config_dir = Path(home_dir) / 'mycelium'
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_file_path() -> Path:
    """Get the configuration file path."""
    return get_config_dir() / 'config.yml'


@dataclass
class PlexConfig:
    """Configuration for Plex connection."""
    url: str = "http://localhost:32400"
    token: Optional[str] = None
    music_library_name: str = "Music"


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
class DatabaseConfig:
    """Configuration for track metadata database."""
    db_path: str = "./mycelium_tracks.db"
    

@dataclass
class APIConfig:
    """Configuration for API server."""
    host: str = "localhost"
    port: int = 8000
    reload: bool = False


@dataclass
class MyceliumConfig:
    """Main configuration class."""
    plex: PlexConfig
    clap: CLAPConfig
    chroma: ChromaConfig
    database: DatabaseConfig
    api: APIConfig

    @classmethod
    def load_from_yaml(cls, config_path: Optional[Path] = None) -> "MyceliumConfig":
        """Load configuration from YAML file with environment variable fallbacks."""
        if config_path is None:
            config_path = get_config_file_path()
        
        # Load YAML config if it exists
        config_data = {}
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
        
        # Apply environment variable overrides
        plex_config = PlexConfig(
            url=os.environ.get("PLEX_URL", config_data.get("plex", {}).get("url", "http://localhost:32400")),
            token=os.environ.get("PLEX_TOKEN", config_data.get("plex", {}).get("token")),
            music_library_name=os.environ.get("PLEX_MUSIC_LIBRARY", config_data.get("plex", {}).get("music_library_name", "Music"))
        )
        
        clap_config = CLAPConfig(
            model_id=os.environ.get("CLAP_MODEL_ID", config_data.get("clap", {}).get("model_id", "laion/larger_clap_music_and_speech")),
            target_sr=int(os.environ.get("CLAP_TARGET_SR", config_data.get("clap", {}).get("target_sr", 48000))),
            chunk_duration_s=int(os.environ.get("CLAP_CHUNK_DURATION", config_data.get("clap", {}).get("chunk_duration_s", 10))),
            batch_size=int(os.environ.get("CLAP_BATCH_SIZE", config_data.get("clap", {}).get("batch_size", 16)))
        )
        
        chroma_config = ChromaConfig(
            db_path=os.environ.get("CHROMA_DB_PATH", config_data.get("chroma", {}).get("db_path", "./music_vector_db")),
            collection_name=os.environ.get("COLLECTION_NAME", config_data.get("chroma", {}).get("collection_name", "my_music_library")),
            batch_size=int(os.environ.get("CHROMA_BATCH_SIZE", config_data.get("chroma", {}).get("batch_size", 1000)))
        )
        
        database_config = DatabaseConfig(
            db_path=os.environ.get("DATABASE_PATH", config_data.get("database", {}).get("db_path", "./mycelium_tracks.db"))
        )
        
        api_config = APIConfig(
            host=os.environ.get("API_HOST", config_data.get("api", {}).get("host", "localhost")),
            port=int(os.environ.get("API_PORT", config_data.get("api", {}).get("port", 8000))),
            reload=os.environ.get("API_RELOAD", str(config_data.get("api", {}).get("reload", False))).lower() == "true"
        )
        
        return cls(
            plex=plex_config,
            clap=clap_config,
            chroma=chroma_config,
            database=database_config,
            api=api_config
        )
    
    def save_to_yaml(self, config_path: Optional[Path] = None) -> None:
        """Save configuration to YAML file."""
        if config_path is None:
            config_path = get_config_file_path()
        
        config_dict = {
            "plex": asdict(self.plex),
            "clap": asdict(self.clap), 
            "chroma": asdict(self.chroma),
            "database": asdict(self.database),
            "api": asdict(self.api)
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)
    
    @classmethod
    def from_env(cls) -> "MyceliumConfig":
        """Create configuration from environment variables (backward compatibility)."""
        return cls.load_from_yaml()
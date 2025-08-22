"""Configuration management for Mycelium"""

import logging
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import yaml


def get_user_data_dir() -> Path:
    """Get the user data directory for Mycelium (platform-specific)."""
    if os.name == 'nt':  # Windows
        base_dir = os.getenv('LOCALAPPDATA', os.path.expanduser('~/AppData/Local'))
    elif os.uname().sysname == 'Darwin':  # macOS
        base_dir = os.path.expanduser('~/Library/Application Support')
    else:  # Linux/Unix
        base_dir = os.getenv('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))

    data_dir = Path(base_dir) / 'mycelium'
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_user_log_dir() -> Path:
    """Get the user log directory for Mycelium (platform-specific)."""
    if os.name == 'nt':  # Windows
        base_dir = os.getenv('LOCALAPPDATA', os.path.expanduser('~/AppData/Local'))
    elif os.uname().sysname == 'Darwin':  # macOS
        base_dir = os.path.expanduser('~/Library/Logs')
    else:  # Linux/Unix
        base_dir = os.getenv('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))

    log_dir = Path(base_dir) / 'mycelium'
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_config_dir() -> Path:
    """Get the configuration directory for Mycelium."""
    if os.name == 'nt':  # Windows
        base_dir = os.getenv('APPDATA', os.path.expanduser('~/AppData/Roaming'))
    else:  # macOS and Linux/Unix
        base_dir = os.path.expanduser('~/.config')

    config_dir = Path(base_dir) / 'mycelium'
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


@dataclass
class ChromaConfig:
    """Configuration for ChromaDB."""
    collection_name: str = "my_music_library"
    batch_size: int = 1000

    @staticmethod
    def get_db_path() -> str:
        """Get the actual database path for ChromaDB."""
        return str(get_user_data_dir() / "music_vector_db")


@dataclass
class DatabaseConfig:
    """Configuration for track metadata database."""

    @staticmethod
    def get_db_path() -> str:
        """Get the actual database path for track metadata."""
        return str(get_user_data_dir() / "mycelium_tracks.db")


@dataclass
class APIConfig:
    """Configuration for API server."""
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False


@dataclass
class LoggingConfig:
    """Configuration for logging system."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None


@dataclass
class MyceliumConfig:
    """Main configuration class."""
    plex: PlexConfig
    clap: CLAPConfig
    chroma: ChromaConfig
    database: DatabaseConfig
    api: APIConfig
    logging: LoggingConfig

    @classmethod
    def load_from_yaml(cls, config_path: Optional[Path] = None) -> "MyceliumConfig":
        """Load configuration"""
        if config_path is None:
            config_path = get_config_file_path()

        # Load YAML config if it exists
        config_data = {}
        config_exists = config_path.exists()
        if config_exists:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}

        plex_config = PlexConfig(
            url=config_data.get("plex", {}).get("url", "http://localhost:32400"),
            token=config_data.get("plex", {}).get("token", "replace_with_your_token"),
            music_library_name=config_data.get("plex", {}).get("music_library_name", "Music")
        )

        clap_config = CLAPConfig(
            model_id=config_data.get("clap", {}).get("model_id", "laion/larger_clap_music_and_speech"),
            target_sr=config_data.get("clap", {}).get("target_sr", 48000),
            chunk_duration_s=config_data.get("clap", {}).get("chunk_duration_s", 10)
        )

        chroma_config = ChromaConfig(
            collection_name=config_data.get("chroma", {}).get("collection_name", "my_music_library"),
            batch_size=config_data.get("chroma", {}).get("batch_size", 1000)
        )

        database_config = DatabaseConfig()

        api_config = APIConfig(
            host=config_data.get("api", {}).get("host", "0.0.0.0"),
            port=config_data.get("api", {}).get("port", 8000),
            reload=config_data.get("api", {}).get("reload", False)
        )

        # Handle logging configuration with default log file path
        logging_data = config_data.get("logging", {})
        log_file = logging_data.get("file")
        if log_file is None:
            log_file = str(get_user_log_dir() / "mycelium.log")

        logging_config = LoggingConfig(
            level=logging_data.get("level", "INFO"),
            format=logging_data.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            file=log_file
        )

        cfg = cls(
            plex=plex_config,
            clap=clap_config,
            chroma=chroma_config,
            database=database_config,
            api=api_config,
            logging=logging_config
        )

        # If no config file existed, create one with current values for convenience
        if not config_exists:
            # Ensure config directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                cfg.save_to_yaml(config_path)
            except Exception:
                # Best-effort; ignore failures to avoid blocking startup
                pass

        return cfg

    def save_to_yaml(self, config_path: Optional[Path] = None) -> None:
        """Save configuration to YAML file."""
        if config_path is None:
            config_path = get_config_file_path()

        config_dict = {
            "plex": asdict(self.plex),
            "clap": asdict(self.clap),
            "chroma": asdict(self.chroma),
            "database": asdict(self.database),
            "api": asdict(self.api),
            "logging": asdict(self.logging)
        }

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)

    def setup_logging(self) -> None:
        """Setup logging configuration."""
        # Configure the root logger
        level = getattr(logging, self.logging.level.upper(), logging.INFO)

        # Create log directory if needed
        log_file_path = Path(self.logging.file)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Setup logging
        logging.basicConfig(
            level=level,
            format=self.logging.format,
            handlers=[
                logging.FileHandler(self.logging.file),
                logging.StreamHandler()  # Also log to console
            ]
        )

        # Set log level for third-party libraries to reduce noise
        logging.getLogger('chromadb').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)


def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration (standalone function for backward compatibility)."""
    log_dir = get_user_log_dir()
    log_file = log_dir / "mycelium.log"
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


# Export all necessary components
__all__ = [
    "MyceliumConfig", 
    "PlexConfig",
    "CLAPConfig", 
    "ChromaConfig",
    "DatabaseConfig",
    "APIConfig",
    "LoggingConfig",
    "get_config_file_path",
    "get_user_data_dir",
    "get_user_log_dir",
    "get_config_dir",
    "setup_logging"
]
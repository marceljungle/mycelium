"""Client-specific YAML configuration management for Mycelium workers."""

import os
import logging
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


def get_client_config_dir() -> Path:
    """Get the configuration directory for Mycelium client."""
    if os.name == 'nt':  # Windows
        base_dir = os.getenv('APPDATA', os.path.expanduser('~/AppData/Roaming'))
    else:  # macOS and Linux/Unix
        base_dir = os.path.expanduser('~/.config')
    
    config_dir = Path(base_dir) / 'mycelium'
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_client_config_file_path() -> Path:
    """Get the client configuration file path."""
    return get_client_config_dir() / 'client_config.yml'


@dataclass
class CLAPConfig:
    """Configuration for CLAP model."""
    model_id: str = "laion/larger_clap_music_and_speech"
    target_sr: int = 48000
    chunk_duration_s: int = 10
    num_chunks: int = 3
    max_load_duration_s: Optional[int] = 120


@dataclass
class ClientConfig:
    """Configuration for client worker connections."""
    server_host: str = "localhost"
    server_port: int = 8000
    download_queue_size: int = 15
    job_queue_size: int = 30
    poll_interval: int = 5
    download_workers: int = 10
    gpu_batch_size: int = 4


@dataclass
class ClientAPIConfig:
    """Configuration for client API server."""
    host: str = "localhost"
    port: int = 3001


@dataclass
class LoggingConfig:
    """Configuration for logging system."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None


@dataclass
class MyceliumClientConfig:
    """Client-specific configuration class containing only settings relevant to GPU workers."""
    clap: CLAPConfig
    client: ClientConfig
    client_api: ClientAPIConfig
    logging: LoggingConfig

    @classmethod
    def load_from_yaml(cls, config_path: Optional[Path] = None) -> "MyceliumClientConfig":
        """Load client configuration from YAML file only."""
        if config_path is None:
            config_path = get_client_config_file_path()
        
        # Load YAML config if it exists
        config_data = {}
        config_exists = config_path.exists()
        if config_exists:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
        
        # Load from YAML only - no environment variable fallbacks
        clap_config = CLAPConfig(
            model_id=config_data.get("clap", {}).get("model_id", "laion/larger_clap_music_and_speech"),
            target_sr=config_data.get("clap", {}).get("target_sr", 48000),
            chunk_duration_s=config_data.get("clap", {}).get("chunk_duration_s", 10),
            num_chunks=config_data.get("clap", {}).get("num_chunks", 3),
            max_load_duration_s=config_data.get("clap", {}).get("max_load_duration_s", 120)
        )
        
        client_config = ClientConfig(
            server_host=config_data.get("client", {}).get("server_host", "localhost"),
            server_port=config_data.get("client", {}).get("server_port", 8000),
            download_queue_size=config_data.get("client", {}).get("download_queue_size", 15),
            job_queue_size=config_data.get("client", {}).get("job_queue_size", 30),
            poll_interval=config_data.get("client", {}).get("poll_interval", 5),
            download_workers=config_data.get("client", {}).get("download_workers", 10),
            gpu_batch_size=config_data.get("client", {}).get("gpu_batch_size", 4),
        )
        
        client_api_config = ClientAPIConfig(
            host=config_data.get("client_api", {}).get("host", "localhost"),
            port=config_data.get("client_api", {}).get("port", 3001)
        )
        
        # Handle logging configuration with default log file path
        logging_data = config_data.get("logging", {})
        log_file = logging_data.get("file")
        if log_file is None:
            log_file = str(get_user_log_dir() / "mycelium_client.log")
        
        logging_config = LoggingConfig(
            level=logging_data.get("level", "INFO"),
            format=logging_data.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            file=log_file
        )
        
        cfg = cls(
            clap=clap_config,
            client=client_config,
            client_api=client_api_config,
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
        """Save client configuration to YAML file."""
        if config_path is None:
            config_path = get_client_config_file_path()
        
        config_dict = {
            "clap": asdict(self.clap), 
            "client": asdict(self.client),
            "client_api": asdict(self.client_api),
            "logging": asdict(self.logging)
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)

    def to_dict(self) -> dict:
        """Convert client configuration to dictionary format."""
        return {
            "client": {
                "server_host": self.client.server_host,
                "server_port": self.client.server_port,
                "download_queue_size": self.client.download_queue_size,
                "job_queue_size": self.client.job_queue_size,
                "poll_interval": self.client.poll_interval,
                "download_workers": self.client.download_workers,
                "gpu_batch_size": self.client.gpu_batch_size
            },
            "client_api": {
                "host": self.client_api.host,
                "port": self.client_api.port
            },
            "clap": {
                "model_id": self.clap.model_id,
                "target_sr": self.clap.target_sr,
                "chunk_duration_s": self.clap.chunk_duration_s,
                "num_chunks": self.clap.num_chunks,
                "max_load_duration_s": self.clap.max_load_duration_s
            },
            "logging": {
                "level": self.logging.level
            }
        }

    def setup_logging(self) -> None:
        """Setup logging configuration."""
        # Configure the root logger
        level = getattr(logging, self.logging.level.upper(), logging.INFO)
        
        # Create log directory if needed
        log_file_path = Path(self.logging.file)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Get the root logger
        root_logger = logging.getLogger()
        
        # Remove all existing handlers to ensure clean reconfiguration
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            handler.close()
        
        # Set the new level on the root logger
        root_logger.setLevel(level)
        
        # Create and add new handlers
        file_handler = logging.FileHandler(self.logging.file)
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(self.logging.format))
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter(self.logging.format))
        
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        # Set log level for third-party libraries to reduce noise
        logging.getLogger('chromadb').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
        
        # Disable verbose numba logging
        logging.getLogger('numba.core').setLevel(logging.WARNING)
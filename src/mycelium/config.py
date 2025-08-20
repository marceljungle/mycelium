"""Configuration management for Mycelium - YAML only."""

import logging

# Import YAML configuration as the only configuration method
from .config_yaml import MyceliumConfig, get_config_file_path, get_user_data_dir, get_user_log_dir


def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration."""
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


# Export the YAML-based configuration as the main one
__all__ = [
    "MyceliumConfig", 
    "get_config_file_path",
    "get_user_data_dir",
    "get_user_log_dir", 
    "setup_logging"
]
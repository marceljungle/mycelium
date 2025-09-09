"""Minimal FastAPI application for Mycelium client configuration."""

import functools
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..client_config import MyceliumClientConfig

# Setup logger for this module
logger = logging.getLogger(__name__)

# Global configuration instance
config = MyceliumClientConfig.load_from_yaml()

# Global lock for thread-safe config reloading
config_lock = threading.RLock()

def with_client_lock(func):
    """Decorator to ensure thread-safe access to client configuration."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        with config_lock:
            return await func(*args, **kwargs)
    return wrapper

def reload_client_config() -> None:
    """Reload client configuration safely."""
    global config
    
    with config_lock:
        try:
            logger.info("Reloading client configuration...")
            
            # Load new configuration
            new_config = MyceliumClientConfig.load_from_yaml()
            
            # Update logging if level changed
            if new_config.logging.level != config.logging.level:
                # Use the proper setup_logging method from the config
                new_config.setup_logging()
                logger.info(f"Updated logging level to {new_config.logging.level}")
            
            # Update global reference atomically
            config = new_config
            
            logger.info("Client configuration reloaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to reload client configuration: {e}", exc_info=True)
            raise


class ConfigRequest(BaseModel):
    """Request model for updating client configuration."""
    client: Dict[str, Any]
    client_api: Dict[str, Any]
    clap: Dict[str, Any]
    logging: Dict[str, Any]


# Create minimal FastAPI app for client configuration only
app = FastAPI(
    title="Mycelium Client API",
    description="Configuration API for Mycelium client workers",
    version="0.1.0"
)

# Add CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=False,  # Must be False when using allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static client frontend files
client_frontend_dist_path = Path(__file__).parent.parent / "client_frontend_dist"
if client_frontend_dist_path.exists():
    # Mount Next.js static assets at their expected path
    next_static_path = client_frontend_dist_path / "_next"
    if next_static_path.exists():
        app.mount("/_next", StaticFiles(directory=str(next_static_path)), name="next_static")
    
    # Mount client frontend application under /app with SPA routing support
    app.mount("/app", StaticFiles(directory=str(client_frontend_dist_path), html=True), name="client_frontend")


@app.get("/")
async def root():
    """Redirect root to client frontend application."""
    return RedirectResponse("/app")


@app.get("/api")
async def api_info():
    """API information endpoint (moved from root to /api)."""
    return {
        "message": "Mycelium Client Configuration API",
        "version": "0.1.0",
        "endpoints": {
            "config_get": "/api/config",
            "config_save": "/api/config"
        }
    }


@app.get("/api/config")
@with_client_lock
async def get_config():
    """Get current client configuration."""
    try:
        logger.info("Client configuration get request received")
        
        # Return current configuration as dict using global config
        config_dict = {
            "client": {
                "server_host": config.client.server_host,
                "server_port": config.client.server_port,
                "download_queue_size": config.client.download_queue_size,
                "job_queue_size": config.client.job_queue_size,
                "poll_interval": config.client.poll_interval,
                "download_workers": config.client.download_workers,
                "gpu_batch_size": config.client.gpu_batch_size
            },
            "client_api": {
                "host": config.client_api.host,
                "port": config.client_api.port
            },
            "clap": {
                "model_id": config.clap.model_id,
                "target_sr": config.clap.target_sr,
                "chunk_duration_s": config.clap.chunk_duration_s,
                "num_chunks": config.clap.num_chunks,
                "max_load_duration_s": config.clap.max_load_duration_s
            },
            "logging": {
                "level": config.logging.level
            }
        }
        logger.info("Client configuration retrieved successfully")
        return config_dict
    except Exception as e:
        logger.error(f"Failed to get client configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get configuration: {str(e)}")


@app.post("/api/config")
async def save_config(config_request: ConfigRequest):
    """Save client configuration to YAML file and hot-reload the application."""
    try:
        logger.info("Client configuration save request received")
        
        # Create new config object with updated values
        from ..client_config import CLAPConfig, ClientConfig, ClientAPIConfig, LoggingConfig
        
        clap_config = CLAPConfig(**config_request.clap)
        client_config = ClientConfig(**config_request.client)
        client_api_config = ClientAPIConfig(**config_request.client_api)
        logging_config = LoggingConfig(**config_request.logging)
        
        yaml_config = MyceliumClientConfig(
            clap=clap_config,
            client=client_config,
            client_api=client_api_config,
            logging=logging_config
        )
        
        # Save to default YAML location
        yaml_config.save_to_yaml()
        logger.info("Client configuration saved successfully to YAML file")
        
        # Hot-reload the configuration
        try:
            reload_client_config()
            logger.info("Client configuration hot-reloaded successfully")
            return {
                "message": "Configuration saved and reloaded successfully! Changes are now active.",
                "status": "success",
                "reloaded": True
            }
        except Exception as reload_error:
            logger.error(f"Client configuration saved but hot-reload failed: {reload_error}", exc_info=True)
            return {
                "message": "Configuration saved successfully, but hot-reload failed. Please restart the client to apply changes.",
                "status": "warning",
                "reloaded": False,
                "reload_error": str(reload_error)
            }
    except Exception as e:
        logger.error(f"Failed to save client configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save configuration: {str(e)}")
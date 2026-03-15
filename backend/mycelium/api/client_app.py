"""Minimal FastAPI application for Mycelium client configuration."""

import asyncio
import functools
import logging
import socket
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from mycelium.api.schemas import (
    ClientStatusResponse,
    SaveConfigResponse,
    WorkerConfigRequest,
    WorkerConfigResponse,
    WorkerProcessingStatus,
)
from mycelium.client_status import worker_status
from ..client_config import (
    CLAPConfig, ClientConfig, ClientAPIConfig, EmbeddingConfig,
    LoggingConfig, MuQConfig, MyceliumClientConfig,
)
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


# Create minimal FastAPI app for client configuration only
app = FastAPI(
    title="Mycelium Client API",
    description="Configuration API for Mycelium client workers"
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


async def _check_server_reachable(host: str, port: int, timeout: float = 3.0) -> bool:
    """Check if the Mycelium server is reachable via TCP."""
    def _check() -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (socket.timeout, socket.error, OSError):
            return False
    return await asyncio.to_thread(_check)


@app.get("/api/status", response_model=ClientStatusResponse)
async def get_status():
    """Return worker processing status and server reachability."""
    try:
        with config_lock:
            host = config.client.server_host
            port = config.client.server_port

        reachable = await _check_server_reachable(host, port)

        status_dict = worker_status.to_dict()
        return ClientStatusResponse(
            server_reachable=reachable,
            worker=WorkerProcessingStatus(**status_dict),
        )
    except Exception as e:
        logger.error(f"Failed to get client status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config", response_model=WorkerConfigResponse)
@with_client_lock
async def get_config():
    """Get current client configuration."""
    try:
        logger.info("Client configuration get request received")
        config_dict = config.to_dict()
        logger.info("Client configuration retrieved successfully")
        return WorkerConfigResponse(**config_dict)
    except Exception as e:
        logger.error(f"Failed to get client configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get configuration: {str(e)}")


@app.post("/api/config", response_model=SaveConfigResponse)
async def save_config(config_request: WorkerConfigRequest):
    """Save client configuration to YAML file and hot-reload the application."""
    try:
        logger.info("Client configuration save request received")
        embedding_config = EmbeddingConfig(
            **dict(config_request.embedding)
        ) if hasattr(config_request, 'embedding') and config_request.embedding else EmbeddingConfig()
        clap_config = CLAPConfig(**dict(config_request.clap))
        muq_config = MuQConfig(
            **dict(config_request.muq)
        ) if hasattr(config_request, 'muq') and config_request.muq else MuQConfig()
        client_config = ClientConfig(**dict(config_request.client))
        client_api_config = ClientAPIConfig(**dict(config_request.client_api))
        logging_config = LoggingConfig(**dict(config_request.logging))
        
        yaml_config = MyceliumClientConfig(
            embedding=embedding_config,
            clap=clap_config,
            muq=muq_config,
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
            return SaveConfigResponse(
                message="Configuration saved and reloaded successfully! Changes are now active.",
                status="success",
                reloaded=True
            )
        except Exception as reload_error:
            logger.error(f"Client configuration saved but hot-reload failed: {reload_error}", exc_info=True)
            return SaveConfigResponse(
                message="Configuration saved successfully, but hot-reload failed. Please restart the client to apply changes.",
                status="warning",
                reloaded=False,
                reload_error=str(reload_error)
            )
    except Exception as e:
        logger.error(f"Failed to save client configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save configuration: {str(e)}")
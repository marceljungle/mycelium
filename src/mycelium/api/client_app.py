"""Minimal FastAPI application for Mycelium client configuration."""

import functools
import yaml
import logging
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from mycelium.api.generated_sources.worker_schemas.models import (
    WorkerConfigRequest,
    WorkerConfigResponse,
    SaveConfigResponse,
)
from ..client_config import CLAPConfig, ClientConfig, ClientAPIConfig, LoggingConfig, MyceliumClientConfig
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

WORKER_SPEC_PATH = Path(__file__).resolve().parents[3] / "openapi" / "worker_openapi.yaml"
app.state.external_openapi_cache = None

def _custom_openapi():
    if app.state.external_openapi_cache is None:
        with WORKER_SPEC_PATH.open("r", encoding="utf-8") as f:
            app.state.external_openapi_cache = yaml.safe_load(f)
    return app.state.external_openapi_cache

app.openapi = _custom_openapi

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


# Serve the API-first OpenAPI YAML (for tooling and validation)
@app.get("/openapi.yaml")
async def get_openapi_yaml():
    """Serve the external API-first OpenAPI YAML if available."""
    if WORKER_SPEC_PATH.exists():
        return FileResponse(path=str(WORKER_SPEC_PATH), media_type="application/yaml")
    raise HTTPException(status_code=404, detail="OpenAPI YAML not found")


@app.get("/")
async def root():
    """Redirect root to client frontend application."""
    return RedirectResponse("/app")


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
        clap_config = CLAPConfig(**dict(config_request.clap))
        client_config = ClientConfig(**dict(config_request.client))
        client_api_config = ClientAPIConfig(**dict(config_request.client_api))
        logging_config = LoggingConfig(**dict(config_request.logging))
        
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
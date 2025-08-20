"""Minimal FastAPI application for Mycelium client configuration."""

import logging
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..config_yaml import MyceliumConfig

# Setup logger for this module
logger = logging.getLogger(__name__)


class ConfigRequest(BaseModel):
    """Request model for updating configuration."""
    plex: Dict[str, Any]
    api: Dict[str, Any]
    client: Dict[str, Any]
    chroma: Dict[str, Any]
    clap: Dict[str, Any]
    logging: Dict[str, Any]
    database: Optional[Dict[str, Any]] = None


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


@app.get("/")
async def root():
    """Root endpoint with basic information."""
    return {
        "message": "Mycelium Client Configuration API",
        "version": "0.1.0",
        "endpoints": {
            "config_get": "/api/config",
            "config_save": "/api/config"
        }
    }


@app.get("/api/config")
async def get_config():
    """Get current configuration."""
    try:
        logger.info("Client configuration get request received")
        # Load current configuration from YAML
        config = MyceliumConfig.load_from_yaml()
        
        # Return current configuration as dict
        config_dict = {
            "plex": {
                "url": config.plex.url,
                "token": config.plex.token,
                "music_library_name": config.plex.music_library_name
            },
            "api": {
                "host": config.api.host,
                "port": config.api.port,
                "reload": config.api.reload
            },
            "client": {
                "server_host": config.client.server_host,
                "server_port": config.client.server_port
            },
            "chroma": {
                "collection_name": config.chroma.collection_name,
                "batch_size": config.chroma.batch_size
            },
            "clap": {
                "model_id": config.clap.model_id,
                "target_sr": config.clap.target_sr,
                "chunk_duration_s": config.clap.chunk_duration_s
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
    """Save configuration to YAML file."""
    try:
        logger.info("Client configuration save request received")
        
        # Create new config object with updated values
        from ..config_yaml import PlexConfig, CLAPConfig, ChromaConfig, DatabaseConfig, APIConfig, ClientConfig, LoggingConfig
        
        plex_config = PlexConfig(**config_request.plex)
        clap_config = CLAPConfig(**config_request.clap)
        chroma_config = ChromaConfig(**config_request.chroma)
        database_config = DatabaseConfig()
        api_config = APIConfig(**config_request.api)
        client_config = ClientConfig(**config_request.client)
        logging_config = LoggingConfig(**config_request.logging)
        
        yaml_config = MyceliumConfig(
            plex=plex_config,
            clap=clap_config,
            chroma=chroma_config,
            database=database_config,
            api=api_config,
            client=client_config,
            logging=logging_config
        )
        
        # Save to default YAML location
        yaml_config.save_to_yaml()
        logger.info("Client configuration saved successfully to YAML file")
        
        return {
            "message": "Configuration saved successfully. Restart the client to apply changes.",
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Failed to save client configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save configuration: {str(e)}")
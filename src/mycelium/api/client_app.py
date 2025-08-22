"""Minimal FastAPI application for Mycelium client configuration."""

import logging
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..client_config import MyceliumClientConfig

# Setup logger for this module
logger = logging.getLogger(__name__)


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
    """Get current client configuration."""
    try:
        logger.info("Client configuration get request received")
        # Load current configuration from YAML
        config = MyceliumClientConfig.load_from_yaml()
        
        # Return current configuration as dict
        config_dict = {
            "client": {
                "server_host": config.client.server_host,
                "server_port": config.client.server_port
            },
            "client_api": {
                "host": config.client_api.host,
                "port": config.client_api.port
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
    """Save client configuration to YAML file."""
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
        
        return {
            "message": "Configuration saved successfully. Restart the client to apply changes.",
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Failed to save client configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save configuration: {str(e)}")
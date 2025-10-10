"""Main entry point for the Mycelium application."""

import atexit
import logging
import threading
from typing import Optional

import typer
from typing_extensions import Annotated

app = typer.Typer(
    name="mycelium-ai",
    help="Mycelium AI - Plex Music Recommendation System",
    no_args_is_help=True
)

logger = logging.getLogger(__name__)

# Global reference for service cleanup
_server_service = None

# Register cleanup on exit
atexit.register(lambda: cleanup_server_resources())


def cleanup_server_resources():
    """Clean up server resources, including model unloading."""
    global _server_service
    if _server_service is not None:
        try:
            logger.info("Cleaning up server resources...")
            _server_service.cleanup()
            logger.info("Server resources cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during server cleanup: {e}")
        finally:
            _server_service = None


def get_server_service():
    """Get the server service instance for cleanup."""
    global _server_service
    if _server_service is None:
        # Import here to get the service from app.py
        from mycelium.api.app import service
        try:
            _server_service = service
            logger.debug("Server service reference acquired for cleanup")
        except ImportError as e:
            logger.warning(f"Could not import service for cleanup: {e}")
        except Exception as e:
            logger.warning(f"Error getting service reference: {e}")
    return _server_service


def run_server_api(config) -> None:
    """Run the FastAPI server."""
    # Lazy import uvicorn only when needed
    import uvicorn
    
    logger.info(f"Starting API server on {config.api.host}:{config.api.port}")
    uvicorn.run(
        "mycelium.api.app:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.reload
    )


def run_server_mode(config) -> None:
    """Run server mode (API + Frontend served by FastAPI)."""
    # Lazy import uvicorn only when needed
    import uvicorn
    
    logger.info("Starting Mycelium Server...")
    
    # Get service reference for cleanup
    get_server_service()

    try:
        logger.info(f"Starting server on {config.api.host}:{config.api.port}")
        logger.info("Frontend will be served at the same address")
        uvicorn.run(
            "mycelium.api.app:app",
            host=config.api.host,
            port=config.api.port
        )
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        cleanup_server_resources()
    except Exception as e:
        logger.error(f"Server error: {e}")
        cleanup_server_resources()
        raise


def run_client_mode(
        client_config
) -> None:
    """Run client mode (GPU worker + Client API with Frontend)."""
    # Lazy import client dependencies only when needed
    import uvicorn
    from mycelium.client import run_client
    
    logger.info("Starting Mycelium Client...")

    client_thread = threading.Thread(
        target=run_client
    )
    client_thread.daemon = True
    client_thread.start()

    # Start the client API server in main thread
    try:
        host = client_config.client_api.host
        port = client_config.client_api.port
        logger.info(f"Starting client API server on {host}:{port}")
        logger.info("Frontend will be served at the same address")
        uvicorn.run(
            "mycelium.api.client_app:app",
            host=host,
            port=port
        )
    except KeyboardInterrupt:
        logger.info("Shutting down client...")


@app.command()
def server() -> None:
    """Start server mode (API + Frontend)."""
    try:
        # Lazy import config only when needed
        from mycelium.config import MyceliumConfig
        
        config = MyceliumConfig.load_from_yaml()
        config.setup_logging()

        run_server_mode(config)
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
        cleanup_server_resources()
        typer.echo("\nServer stopped")
        raise typer.Exit(130)
    except Exception as e:
        cleanup_server_resources()
        typer.echo(f"Server error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def client() -> None:
    """Start client mode (GPU worker)."""
    try:
        # Lazy import client config only when needed
        from mycelium.client_config import MyceliumClientConfig
        
        client_config = MyceliumClientConfig.load_from_yaml()
        client_config.setup_logging()

        run_client_mode(
            client_config=client_config
        )
    except Exception as e:
        typer.echo(f"Client error: {e}", err=True)
        raise typer.Exit(1)


def main() -> None:
    """Main entry point for the CLI application."""
    try:
        app()
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        cleanup_server_resources()
        typer.echo("\nOperation cancelled by user")
        raise typer.Exit(130)
    except Exception:
        cleanup_server_resources()
        raise


if __name__ == "__main__":
    main()

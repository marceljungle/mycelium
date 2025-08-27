"""Main entry point for the Mycelium application."""

import atexit
import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

import typer
import uvicorn
from typing_extensions import Annotated

from mycelium.client import run_client
from mycelium.client_config import MyceliumClientConfig
from mycelium.config import MyceliumConfig

app = typer.Typer(
    name="mycelium",
    help="Mycelium - Plex Music Recommendation System",
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


def run_server_api(config: MyceliumConfig) -> None:
    """Run the FastAPI server."""
    logger.info(f"Starting API server on {config.api.host}:{config.api.port}")
    uvicorn.run(
        "mycelium.api.app:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.reload
    )


def run_frontend(server_config: MyceliumConfig = None,
                 client_config: MyceliumClientConfig = None):
    """Run the frontend server."""
    frontend_dir = Path(__file__).parent.parent.parent / "frontend"
    if not frontend_dir.exists():
        logger.warning("Frontend directory not found. Skipping frontend server.")
        return

    # Set environment variable for client mode
    env = dict(os.environ)
    if client_config:
        env['NEXT_PUBLIC_MYCELIUM_MODE'] = 'client'
        env['NEXT_PUBLIC_API_PORT'] = str(client_config.client_api.port)
    else:
        env['NEXT_PUBLIC_MYCELIUM_MODE'] = 'server'
        env['NEXT_PUBLIC_API_PORT'] = str(server_config.api.port)

    logger.info("Starting frontend development server...")
    try:
        # TODO: Before release, this should be run with build and start
        subprocess.run(["npm", "run", "dev"], cwd=frontend_dir, check=True, env=env)
    except subprocess.CalledProcessError as e:
        logger.error(f"Frontend dev server failed with exit code {e.returncode}")
        return


def run_server_mode(config: MyceliumConfig) -> None:
    """Run server mode (API + Frontend)."""
    logger.info("Starting Mycelium Server...")

    # Start API server in a separate thread
    api_thread = threading.Thread(target=run_server_api, args=(config,))
    api_thread.daemon = True
    api_thread.start()

    # Give the API server time to start and initialize
    time.sleep(2)
    
    # Get service reference for cleanup
    get_server_service()

    # Start frontend (this will run in the main thread)
    try:
        run_frontend(server_config=config)
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        cleanup_server_resources()
    except Exception as e:
        logger.error(f"Frontend error: {e}")
        cleanup_server_resources()
        raise


def run_client_api(client_config: MyceliumClientConfig) -> None:
    """Run the minimal client API server for configuration."""
    host = client_config.client_api.host
    port = client_config.client_api.port
    logger.info(f"Starting client API server on {host}:{port}")
    uvicorn.run(
        "mycelium.api.client_app:app",
        host=host,
        port=port,
        reload=False
    )


def run_client_mode(
        server_host: str = "localhost",
        server_port: int = 8000
) -> None:
    """Run client mode (GPU worker + Client API + Frontend)."""
    logger.info("Starting Mycelium Client...")

    # Load client-specific config
    client_config = MyceliumClientConfig.load_from_yaml()

    # Override client config with provided values
    client_config.client.server_host = server_host
    client_config.client.server_port = server_port

    # Start client API server in a separate thread
    client_api_thread = threading.Thread(
        target=run_client_api,
        args=(client_config,)
    )
    client_api_thread.daemon = True
    client_api_thread.start()

    # Start client worker in a separate thread
    client_thread = threading.Thread(
        target=run_client
    )
    client_thread.daemon = True
    client_thread.start()

    # Start frontend in client mode (this will run in the main thread)
    try:
        run_frontend(client_config=client_config)
    except KeyboardInterrupt:
        logger.info("Shutting down client...")


@app.command()
def server(
        host: Annotated[Optional[str], typer.Option(help="Host to bind to (overrides config)")] = None,
        port: Annotated[Optional[int], typer.Option(help="Port to bind to (overrides config)")] = None,
        reload: Annotated[Optional[bool], typer.Option(help="Enable auto-reload (overrides config)")] = None
) -> None:
    """Start server mode (API + Frontend)."""
    try:
        config = MyceliumConfig.load_from_yaml()
        config.setup_logging()

        # Override API config if provided
        if host is not None:
            config.api.host = host
        if port is not None:
            config.api.port = port
        if reload is not None:
            config.api.reload = reload

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
def client(
        server_host: Annotated[
            Optional[str], typer.Option("--server-host", help="Server host to connect to (overrides config)")] = None,
        server_port: Annotated[
            Optional[int], typer.Option("--server-port", help="Server port to connect to (overrides config)")] = None
) -> None:
    """Start client mode (GPU worker)."""
    try:
        client_config = MyceliumClientConfig.load_from_yaml()
        client_config.setup_logging()

        # Use config defaults if not provided
        final_host = server_host if server_host is not None else client_config.client.server_host
        final_port = server_port if server_port is not None else client_config.client.server_port

        run_client_mode(
            server_host=final_host,
            server_port=final_port
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
    except Exception as e:
        cleanup_server_resources()
        raise


if __name__ == "__main__":
    main()

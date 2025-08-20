"""Main entry point for the Mycelium application."""

import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Optional

import typer
import uvicorn
from typing_extensions import Annotated

from mycelium.client import run_client
from mycelium.client_config_yaml import MyceliumClientConfig
from mycelium.config_yaml import MyceliumConfig

app = typer.Typer(
    name="mycelium",
    help="Mycelium - Plex Music Recommendation System",
    no_args_is_help=True
)

logger = logging.getLogger(__name__)


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

    # Start frontend (this will run in the main thread)
    try:
        run_frontend(server_config=config)
    except KeyboardInterrupt:
        logger.info("Shutting down server...")


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
        server_port: int = 8000,
        model_id: str = "laion/larger_clap_music_and_speech"
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
        target=run_client, 
        args=(server_host, server_port, model_id)
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
    except Exception as e:
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
            server_port=final_port,
            model_id=client_config.clap.model_id
        )
    except Exception as e:
        typer.echo(f"Client error: {e}", err=True)
        raise typer.Exit(1)


def main() -> None:
    """Main entry point for the CLI application."""
    try:
        app()
    except KeyboardInterrupt:
        typer.echo("\nOperation cancelled by user")
        raise typer.Exit(130)


if __name__ == "__main__":
    main()

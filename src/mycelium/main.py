"""Main entry point for the Mycelium application."""

import logging
import subprocess
import threading
from pathlib import Path
from typing import Optional

import typer
import uvicorn
from typing_extensions import Annotated

from mycelium.client import run_client
from mycelium.config_yaml import MyceliumConfig

app = typer.Typer(
    name="mycelium",
    help="Mycelium - Plex Music Recommendation System",
    no_args_is_help=True
)

logger = logging.getLogger(__name__)


def run_api(config: MyceliumConfig) -> None:
    """Run the FastAPI server."""
    logger.info(f"Starting API server on {config.api.host}:{config.api.port}")
    uvicorn.run(
        "mycelium.api.app:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.reload
    )


def run_frontend(config: MyceliumConfig):
    """Run the frontend server."""
    frontend_dir = Path(__file__).parent.parent.parent / "frontend"
    if not frontend_dir.exists():
        logger.warning("Frontend directory not found. Skipping frontend server.")
        return

    if config.api.reload:
        build_dir = frontend_dir / ".next"
        build_id = build_dir / "BUILD_ID"

        should_build = not (build_dir.exists() and build_id.exists())

        if should_build:
            logger.info("Building frontend for production...")
            try:
                subprocess.run(["npm", "run", "build"], cwd=frontend_dir, check=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"Frontend build failed with exit code {e.returncode}")
                return
        else:
            logger.info("Reusing existing production build.")

        logger.info("Starting frontend in production...")
        try:
            subprocess.run(["npm", "run", "start"], cwd=frontend_dir, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Frontend start failed with exit code {e.returncode}")
            return
    else:
        logger.info("Starting frontend development server...")
        try:
            subprocess.run(["npm", "run", "dev"], cwd=frontend_dir, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Frontend dev server failed with exit code {e.returncode}")
            return


def run_server_mode(config: MyceliumConfig) -> None:
    """Run server mode (API + Frontend)."""
    logger.info("Starting Mycelium Server...")

    # Start API server in a separate thread
    api_thread = threading.Thread(target=run_api, args=(config,))
    api_thread.daemon = True
    api_thread.start()

    # Start frontend (this will run in the main thread)
    try:
        run_frontend(config)
    except KeyboardInterrupt:
        logger.info("Shutting down server...")


def run_client_mode(
        server_host: str = "localhost",
        server_port: int = 8000,
        model_id: str = "laion/larger_clap_music_and_speech"
) -> None:
    """Run client mode (GPU worker)."""
    logger.info("Starting Mycelium Client...")
    run_client(server_host, server_port, model_id)


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
        config = MyceliumConfig.load_from_yaml()
        config.setup_logging()

        # Use config defaults if not provided
        final_host = server_host if server_host is not None else config.client.server_host
        final_port = server_port if server_port is not None else config.client.server_port

        run_client_mode(
            server_host=final_host,
            server_port=final_port,
            model_id=config.client.model_id
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

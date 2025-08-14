"""Main entry point for the Mycelium application."""

import subprocess
import threading
import time
import logging
from pathlib import Path
from typing import Optional

import typer
import uvicorn
from typing_extensions import Annotated

from mycelium.application.services import MyceliumService
from mycelium.client import run_client
from mycelium.config_yaml import MyceliumConfig

# Create the main Typer app
app = typer.Typer(
    name="mycelium",
    help="Mycelium - Plex Music Recommendation System",
    no_args_is_help=True
)

# Initialize logger
logger = logging.getLogger(__name__)


def scan_library(service: MyceliumService) -> None:
    """Scan the Plex music library."""
    logger.info("Scanning Plex music library...")
    tracks = service.scan_library()
    logger.info(f"Found {len(tracks)} tracks in the library")

    # Show sample of tracks
    if tracks:
        logger.info("Sample tracks:")
        for track in tracks[:5]:
            logger.info(f"  - {track.artist} - {track.title} ({track.album})")


def process_library(service: MyceliumService) -> None:
    """Process the entire library (scan, generate embeddings, index)."""
    logger.info("Starting full library processing...")
    service.full_library_processing()


def search_by_text(service: MyceliumService, query: str, n_results: int = 10) -> None:
    """Search for music by text description."""
    logger.info(f"Searching for: '{query}'")
    results = service.search_similar_by_text(query, n_results)

    if results:
        logger.info(f"Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            logger.info(f"{i}. {result.track.artist} - {result.track.title}")
            logger.info(f"   Album: {result.track.album}")
            logger.info(f"   Similarity: {result.similarity_score:.4f}")
    else:
        logger.info("No results found.")


def search_by_audio(service: MyceliumService, filepath: str, n_results: int = 10) -> None:
    """Search for music similar to an audio file."""
    audio_path = Path(filepath)
    if not audio_path.exists():
        logger.error(f"Audio file '{filepath}' not found")
        return

    logger.info(f"Searching for music similar to: {audio_path.name}")
    results = service.search_similar_by_audio(audio_path, n_results)

    if results:
        logger.info(f"Found {len(results)} similar tracks:")
        for i, result in enumerate(results, 1):
            logger.info(f"{i}. {result.track.artist} - {result.track.title}")
            logger.info(f"   Album: {result.track.album}")
            logger.info(f"   Similarity: {result.similarity_score:.4f}")
    else:
        logger.info("No similar tracks found.")


def show_stats(service: MyceliumService) -> None:
    """Show database statistics."""
    stats = service.get_database_stats()
    logger.info("Database Statistics:")
    logger.info(f"  Total embeddings: {stats['total_embeddings']}")
    logger.info(f"  Collection name: {stats['collection_name']}")
    logger.info(f"  Database path: {stats['database_path']}")


def run_api(config: MyceliumConfig) -> None:
    """Run the FastAPI server."""
    logger.info(f"Starting API server on {config.api.host}:{config.api.port}")
    uvicorn.run(
        "mycelium.api.app:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.reload
    )


def run_frontend():
    """Run the frontend development server."""
    frontend_dir = Path(__file__).parent.parent.parent / "frontend"
    if frontend_dir.exists():
        logger.info("Starting frontend development server...")
        subprocess.run(["npm", "run", "dev"], cwd=frontend_dir)
    else:
        logger.warning("Frontend directory not found. Skipping frontend server.")


def run_server_mode(config: MyceliumConfig) -> None:
    """Run server mode (API + Frontend)."""
    logger.info("Starting Mycelium Server...")

    # Start API server in a separate thread
    api_thread = threading.Thread(target=run_api, args=(config,))
    api_thread.daemon = True
    api_thread.start()

    # Give API server time to start
    time.sleep(2)

    # Start frontend (this will run in the main thread)
    try:
        run_frontend()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")


def run_client_mode(
        server_host: str = "localhost",
        server_port: int = 8000,
        model_id: str = "laion/clap-htsat-unfused"
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
        server_host: Annotated[Optional[str], typer.Option("--server-host", help="Server host to connect to (overrides config)")] = None,
        server_port: Annotated[Optional[int], typer.Option("--server-port", help="Server port to connect to (overrides config)")] = None,
        model_id: Annotated[Optional[str], typer.Option("--model-id", help="CLAP model to use (overrides config)")] = None
) -> None:
    """Start client mode (GPU worker)."""
    try:
        config = MyceliumConfig.load_from_yaml()
        config.setup_logging()
        
        # Use config defaults if not provided
        final_host = server_host if server_host is not None else config.client.server_host
        final_port = server_port if server_port is not None else config.client.server_port
        final_model = model_id if model_id is not None else config.client.model_id
        
        run_client_mode(
            server_host=final_host,
            server_port=final_port,
            model_id=final_model
        )
    except Exception as e:
        typer.echo(f"Client error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def scan() -> None:
    """Scan the Plex music library."""
    try:
        config = MyceliumConfig.load_from_yaml()
        config.setup_logging()
        service = MyceliumService(
            plex_url=config.plex.url,
            plex_token=config.plex.token,
            music_library_name=config.plex.music_library_name,
            db_path=config.chroma.get_db_path(),
            collection_name=config.chroma.collection_name,
            model_id=config.clap.model_id,
            track_db_path=config.database.get_db_path()
        )
        scan_library(service)
    except Exception as e:
        typer.echo(f"Scan error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def process() -> None:
    """Process the entire library (scan + generate embeddings + index)."""
    try:
        config = MyceliumConfig.load_from_yaml()
        config.setup_logging()
        service = MyceliumService(
            plex_url=config.plex.url,
            plex_token=config.plex.token,
            music_library_name=config.plex.music_library_name,
            db_path=config.chroma.get_db_path(),
            collection_name=config.chroma.collection_name,
            model_id=config.clap.model_id,
            track_db_path=config.database.get_db_path()
        )
        process_library(service)
    except Exception as e:
        typer.echo(f"Process error: {e}", err=True)
        raise typer.Exit(1)


@app.command("search-text")
def search_text(
        query: Annotated[str, typer.Argument(help="Text description to search for")],
        results: Annotated[int, typer.Option("--results", "-n", help="Number of results to return")] = 10
) -> None:
    """Search for music by text description."""
    try:
        config = MyceliumConfig.load_from_yaml()
        config.setup_logging()
        service = MyceliumService(
            plex_url=config.plex.url,
            plex_token=config.plex.token,
            music_library_name=config.plex.music_library_name,
            db_path=config.chroma.get_db_path(),
            collection_name=config.chroma.collection_name,
            model_id=config.clap.model_id,
            track_db_path=config.database.get_db_path()
        )
        search_by_text(service, query, results)
    except Exception as e:
        typer.echo(f"Search error: {e}", err=True)
        raise typer.Exit(1)


@app.command("search-audio")
def search_audio(
        filepath: Annotated[str, typer.Argument(help="Path to the audio file")],
        results: Annotated[int, typer.Option("--results", "-n", help="Number of results to return")] = 10
) -> None:
    """Search for music similar to an audio file."""
    try:
        config = MyceliumConfig.load_from_yaml()
        config.setup_logging()
        service = MyceliumService(
            plex_url=config.plex.url,
            plex_token=config.plex.token,
            music_library_name=config.plex.music_library_name,
            db_path=config.chroma.get_db_path(),
            collection_name=config.chroma.collection_name,
            model_id=config.clap.model_id,
            track_db_path=config.database.get_db_path()
        )
        search_by_audio(service, filepath, results)
    except Exception as e:
        typer.echo(f"Search error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def stats() -> None:
    """Show database statistics."""
    try:
        config = MyceliumConfig.load_from_yaml()
        config.setup_logging()
        service = MyceliumService(
            plex_url=config.plex.url,
            plex_token=config.plex.token,
            music_library_name=config.plex.music_library_name,
            db_path=config.chroma.get_db_path(),
            collection_name=config.chroma.collection_name,
            model_id=config.clap.model_id,
            track_db_path=config.database.get_db_path()
        )
        show_stats(service)
    except Exception as e:
        typer.echo(f"Stats error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def api(
        host: Annotated[Optional[str], typer.Option(help="Host to bind to (overrides config)")] = None,
        port: Annotated[Optional[int], typer.Option(help="Port to bind to (overrides config)")] = None,
        reload: Annotated[Optional[bool], typer.Option(help="Enable auto-reload (overrides config)")] = None
) -> None:
    """Start the API server only."""
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

        run_api(config)
    except Exception as e:
        typer.echo(f"API error: {e}", err=True)
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

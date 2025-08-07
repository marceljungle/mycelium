"""Main entry point for the Mycelium application."""

import subprocess
import threading
import time
from pathlib import Path

import typer
import uvicorn
from typing_extensions import Annotated

from mycelium.application.services import MyceliumService
from mycelium.client import run_client
from mycelium.config import MyceliumConfig

# Create the main Typer app
app = typer.Typer(
    name="mycelium",
    help="Mycelium - Plex Music Recommendation System",
    no_args_is_help=True
)


def scan_library(service: MyceliumService) -> None:
    """Scan the Plex music library."""
    print("Scanning Plex music library...")
    tracks = service.scan_library()
    print(f"Found {len(tracks)} tracks in the library")

    # Show sample of tracks
    if tracks:
        print("\nSample tracks:")
        for track in tracks[:5]:
            print(f"  - {track.artist} - {track.title} ({track.album})")


def process_library(service: MyceliumService) -> None:
    """Process the entire library (scan, generate embeddings, index)."""
    print("Starting full library processing...")
    service.full_library_processing()


def search_by_text(service: MyceliumService, query: str, n_results: int = 10) -> None:
    """Search for music by text description."""
    print(f"Searching for: '{query}'")
    results = service.search_similar_by_text(query, n_results)

    if results:
        print(f"\nFound {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result.track.artist} - {result.track.title}")
            print(f"   Album: {result.track.album}")
            print(f"   Similarity: {result.similarity_score:.4f}")
            print()
    else:
        print("No results found.")


def search_by_audio(service: MyceliumService, filepath: str, n_results: int = 10) -> None:
    """Search for music similar to an audio file."""
    audio_path = Path(filepath)
    if not audio_path.exists():
        print(f"Error: Audio file '{filepath}' not found")
        return

    print(f"Searching for music similar to: {audio_path.name}")
    results = service.search_similar_by_audio(audio_path, n_results)

    if results:
        print(f"\nFound {len(results)} similar tracks:")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result.track.artist} - {result.track.title}")
            print(f"   Album: {result.track.album}")
            print(f"   Similarity: {result.similarity_score:.4f}")
            print()
    else:
        print("No similar tracks found.")


def show_stats(service: MyceliumService) -> None:
    """Show database statistics."""
    stats = service.get_database_stats()
    print("Database Statistics:")
    print(f"  Total embeddings: {stats['total_embeddings']}")
    print(f"  Collection name: {stats['collection_name']}")
    print(f"  Database path: {stats['database_path']}")


def run_api(config: MyceliumConfig) -> None:
    """Run the FastAPI server."""

    print(f"Starting API server on {config.api.host}:{config.api.port}")
    uvicorn.run(
        "mycelium.api.app:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.reload
    )


def run_frontend(reload: bool = False):
    """Run the frontend development server."""
    frontend_dir = Path(__file__).parent.parent.parent / "frontend"
    if not frontend_dir.exists():
        print("Frontend directory not found. Skipping frontend server.")
        return

    if reload:
        print("Starting frontend development server (hot reload enabled)...")
        subprocess.run(["npm", "run", "dev"], cwd=frontend_dir)
    else:
        print("Building frontend for production...")
        build_result = subprocess.run(["npm", "run", "build"], cwd=frontend_dir)
        if build_result.returncode == 0:
            print("Starting frontend production server...")
            subprocess.run(["npm", "run", "start"], cwd=frontend_dir)
        else:
            print("Frontend build failed. Falling back to development server...")
            subprocess.run(["npm", "run", "dev"], cwd=frontend_dir)


def run_server_mode(config: MyceliumConfig) -> None:
    """Run server mode (API + Frontend)."""
    print("Starting Mycelium Server...")

    if config.api.reload:
        # In reload mode, run API in main thread and frontend in background
        print("Reload mode: Starting API server in main thread...")

        # Start frontend in background thread
        frontend_thread = threading.Thread(target=run_frontend, args=(config.api.reload,))
        frontend_thread.daemon = True
        frontend_thread.start()

        # Give frontend time to start
        time.sleep(2)

        # Run API in main thread (required for reload/signal handling)
        run_api(config)
    else:
        # In production mode, run API in background and frontend in main thread
        api_thread = threading.Thread(target=run_api, args=(config,))
        api_thread.daemon = True
        api_thread.start()

        # Give API server time to start
        time.sleep(2)

        # Start frontend (this will run in the main thread)
        try:
            run_frontend(config.api.reload)
        except KeyboardInterrupt:
            print("\nShutting down server...")


def run_client_mode(
        server_host: str = "localhost",
        server_port: int = 8000,
        model_id: str = "laion/clap-htsat-unfused"
) -> None:
    """Run client mode (GPU worker)."""
    print("Starting Mycelium Client...")
    run_client(server_host, server_port, model_id)


@app.command()
def server(
        host: Annotated[str, typer.Option(help="Host to bind to")] = "localhost",
        port: Annotated[int, typer.Option(help="Port to bind to")] = 8000,
        reload: Annotated[bool, typer.Option(help="Enable auto-reload")] = False
) -> None:
    """Start server mode (API + Frontend)."""
    try:
        # TODO: have a configuration file for this, no .evns.
        config = MyceliumConfig.from_env()

        # Override API config if provided
        config.api.host = host
        config.api.port = port
        config.api.reload = reload

        run_server_mode(config)
    except Exception as e:
        typer.echo(f"Server error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def client(
        server_host: Annotated[str, typer.Option("--server-host", help="Server host to connect to")] = "localhost",
        server_port: Annotated[int, typer.Option("--server-port", help="Server port to connect to")] = 8000,
        model_id: Annotated[str, typer.Option("--model-id", help="CLAP model to use")] = "laion/clap-htsat-unfused"
) -> None:
    """Start client mode (GPU worker)."""
    try:
        run_client_mode(
            server_host=server_host,
            server_port=server_port,
            model_id=model_id
        )
    except Exception as e:
        typer.echo(f"Client error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def scan() -> None:
    """Scan the Plex music library."""
    try:
        config = MyceliumConfig.from_env()
        service = MyceliumService(
            plex_url=config.plex.url,
            plex_token=config.plex.token,
            music_library_name=config.plex.music_library_name,
            db_path=config.chroma.db_path,
            collection_name=config.chroma.collection_name,
            model_id=config.clap.model_id
        )
        scan_library(service)
    except Exception as e:
        typer.echo(f"Scan error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def process() -> None:
    """Process the entire library (scan + generate embeddings + index)."""
    try:
        config = MyceliumConfig.from_env()
        service = MyceliumService(
            plex_url=config.plex.url,
            plex_token=config.plex.token,
            music_library_name=config.plex.music_library_name,
            db_path=config.chroma.db_path,
            collection_name=config.chroma.collection_name,
            model_id=config.clap.model_id
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
        config = MyceliumConfig.from_env()
        service = MyceliumService(
            plex_url=config.plex.url,
            plex_token=config.plex.token,
            music_library_name=config.plex.music_library_name,
            db_path=config.chroma.db_path,
            collection_name=config.chroma.collection_name,
            model_id=config.clap.model_id
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
        config = MyceliumConfig.from_env()
        service = MyceliumService(
            plex_url=config.plex.url,
            plex_token=config.plex.token,
            music_library_name=config.plex.music_library_name,
            db_path=config.chroma.db_path,
            collection_name=config.chroma.collection_name,
            model_id=config.clap.model_id
        )
        search_by_audio(service, filepath, results)
    except Exception as e:
        typer.echo(f"Search error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def stats() -> None:
    """Show database statistics."""
    try:
        config = MyceliumConfig.from_env()
        service = MyceliumService(
            plex_url=config.plex.url,
            plex_token=config.plex.token,
            music_library_name=config.plex.music_library_name,
            db_path=config.chroma.db_path,
            collection_name=config.chroma.collection_name,
            model_id=config.clap.model_id
        )
        show_stats(service)
    except Exception as e:
        typer.echo(f"Stats error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def api(
        host: Annotated[str, typer.Option(help="Host to bind to")] = "localhost",
        port: Annotated[int, typer.Option(help="Port to bind to")] = 8000,
        reload: Annotated[bool, typer.Option(help="Enable auto-reload")] = False
) -> None:
    """Start the API server only (legacy command)."""
    try:
        config = MyceliumConfig.from_env()

        # Override API config if provided
        config.api.host = host
        config.api.port = port
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

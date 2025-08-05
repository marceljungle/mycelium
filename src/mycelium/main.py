"""Main entry point for the Mycelium application."""

import argparse
import sys
from pathlib import Path

from .application.services import MyceliumService
from .config import MyceliumConfig


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
    import uvicorn
    print(f"Starting API server on {config.api.host}:{config.api.port}")
    uvicorn.run(
        "mycelium.api.app:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.reload
    )


def main() -> None:
    """Main entry point for the CLI application."""
    parser = argparse.ArgumentParser(description="Mycelium - Plex Music Recommendation System")
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Scan library command
    subparsers.add_parser('scan', help='Scan the Plex music library')
    
    # Process library command
    subparsers.add_parser('process', help='Process the entire library (scan + generate embeddings + index)')
    
    # Search by text command
    search_text_parser = subparsers.add_parser('search-text', help='Search for music by text description')
    search_text_parser.add_argument('query', help='Text description to search for')
    search_text_parser.add_argument('--results', '-n', type=int, default=10, help='Number of results to return')
    
    # Search by audio command
    search_audio_parser = subparsers.add_parser('search-audio', help='Search for music similar to an audio file')
    search_audio_parser.add_argument('filepath', help='Path to the audio file')
    search_audio_parser.add_argument('--results', '-n', type=int, default=10, help='Number of results to return')
    
    # Stats command
    subparsers.add_parser('stats', help='Show database statistics')
    
    # API command
    api_parser = subparsers.add_parser('api', help='Start the API server')
    api_parser.add_argument('--host', default='localhost', help='Host to bind to')
    api_parser.add_argument('--port', type=int, default=8000, help='Port to bind to')
    api_parser.add_argument('--reload', action='store_true', help='Enable auto-reload')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Load configuration
    try:
        config = MyceliumConfig.from_env()
    except Exception as e:
        print(f"Configuration error: {e}")
        print("Make sure PLEX_TOKEN environment variable is set.")
        sys.exit(1)
    
    # Override API config if provided
    if args.command == 'api':
        if hasattr(args, 'host'):
            config.api.host = args.host
        if hasattr(args, 'port'):
            config.api.port = args.port
        if hasattr(args, 'reload'):
            config.api.reload = args.reload
    
    # Initialize service (except for API command which initializes its own)
    if args.command != 'api':
        try:
            service = MyceliumService(
                plex_url=config.plex.url,
                plex_token=config.plex.token,
                music_library_name=config.plex.music_library_name,
                db_path=config.chroma.db_path,
                collection_name=config.chroma.collection_name,
                model_id=config.clap.model_id
            )
        except Exception as e:
            print(f"Service initialization error: {e}")
            sys.exit(1)
    
    # Execute command
    try:
        if args.command == 'scan':
            scan_library(service)
        elif args.command == 'process':
            process_library(service)
        elif args.command == 'search-text':
            search_by_text(service, args.query, args.results)
        elif args.command == 'search-audio':
            search_by_audio(service, args.filepath, args.results)
        elif args.command == 'stats':
            show_stats(service)
        elif args.command == 'api':
            run_api(config)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
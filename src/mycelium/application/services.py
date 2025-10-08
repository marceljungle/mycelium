"""Application services for orchestrating business logic."""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from mycelium.application.search_use_cases import (
    MusicSearchUseCase
)
from mycelium.application.library_management_use_cases import (
    LibraryScanUseCase,
    EmbeddingProcessingUseCase,
    ProcessingProgressUseCase,
    WorkerBasedProcessingUseCase
)
from mycelium.config import MyceliumConfig
from mycelium.domain.models import Playlist
from mycelium.domain.models import Track, TrackEmbedding, SearchResult
from mycelium.infrastructure.plex_adapter import PlexMusicRepository
from mycelium.infrastructure.clap_adapter import CLAPEmbeddingGenerator
from mycelium.infrastructure.chroma_adapter import ChromaEmbeddingRepository
from mycelium.infrastructure import (
    TrackDatabase
)


class MyceliumService:
    """Main service for orchestrating the Mycelium application."""

    def __init__(
            self,
            config: MyceliumConfig
    ):
        self._config = config
        self.worker_processing = None
        self.logger = logging.getLogger(__name__)

        # Initialize repositories and adapters
        self.media_server_repository = PlexMusicRepository(
            plex_url=config.plex.url,
            plex_token=config.plex.token,
            music_library_name=config.plex.music_library_name
        )

        self.embedding_generator = CLAPEmbeddingGenerator(model_id=config.clap.model_id,
                                                          target_sr=config.clap.target_sr,
                                                          chunk_duration_s=config.clap.chunk_duration_s,
                                                          num_chunks=config.clap.num_chunks,
                                                          max_load_duration_s=config.clap.max_load_duration_s)

        self.embedding_repository = ChromaEmbeddingRepository(
            db_path=config.chroma.get_db_path(),
            collection_name=config.chroma.collection_name,
            model_id=config.clap.model_id,
            batch_size=config.chroma.batch_size,
            media_server_type=config.media_server.type
        )

        self.track_database = TrackDatabase(db_path=config.database.get_db_path(),
                                            media_server_type=config.media_server.type)

        self.music_search = MusicSearchUseCase(
            embedding_repository=self.embedding_repository,
            embedding_generator=self.embedding_generator
        )

        self.separated_scan = LibraryScanUseCase(
            media_server_repository=self.media_server_repository,
            track_database=self.track_database
        )
        self.resumable_processing = EmbeddingProcessingUseCase(
            embedding_generator=self.embedding_generator,
            embedding_repository=self.embedding_repository,
            track_database=self.track_database,
            model_id=config.clap.model_id,
            gpu_batch_size=config.server.gpu_batch_size
        )
        self.progress_tracker = ProcessingProgressUseCase(track_database=self.track_database)

        # Processing state tracking
        self._processing_in_progress = False



    def scan_library_to_database(self, progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """Scan the Plex library and store metadata to database."""
        return self.separated_scan.execute(progress_callback)

    def process_embeddings_from_database(
            self,
            progress_callback: Optional[callable] = None,
            max_tracks: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process embeddings for unprocessed tracks from database."""
        if self._processing_in_progress:
            return {
                "message": "Processing is already in progress",
                "status": "already_running"
            }

        self._processing_in_progress = True
        try:
            # Reset stop flag for new session
            self.reset_processing_stop_flag()
            result = self.resumable_processing.process_embeddings(progress_callback=progress_callback,
                                                                  max_tracks=max_tracks)
            return result
        finally:
            self._processing_in_progress = False

    def stop_processing(self) -> None:
        """Stop the current embedding processing."""
        # Stop server-side processing
        self.resumable_processing.stop()

        # Stop worker-based processing if available
        if hasattr(self, 'worker_processing'):
            self.stop_worker_processing()

    def reset_processing_stop_flag(self) -> None:
        """Reset the stop flag for new processing session."""
        self.resumable_processing.reset_stop_flag()

    def is_processing_active(self) -> bool:
        """Check if any processing is currently active (server or worker)."""
        return self._processing_in_progress or self.has_active_worker_processing()

    def get_processing_progress(self, model_id: Optional[str] = None) -> Dict[str, Any]:
        """Get current processing progress and statistics."""
        if model_id is None:
            model_id = self.embedding_repository.model_id
        stats = self.progress_tracker.get_current_stats(model_id)
        # Processing is active if either server-side processing is running OR workers have active tasks
        stats["is_processing"] = self.is_processing_active()
        return stats

    def search_similar_by_audio(
            self,
            filepath: Path,
            n_results: int = 10
    ) -> List[SearchResult]:
        """Search for similar tracks by audio file."""
        return self.music_search.search_by_audio_file(filepath, n_results)

    def search_similar_by_text(
            self,
            query: str,
            n_results: int = 10
    ) -> List[SearchResult]:
        """Search for tracks by text description."""
        return self.music_search.search_by_text(query, n_results)

    def search_similar_by_track_id(
            self,
            track_id: str,
            n_results: int = 10
    ) -> List[SearchResult]:
        """Search for tracks similar to a given track ID."""
        return self.music_search.search_by_track_id(track_id=track_id,
                                                    n_results=n_results)

    def get_database_stats(self) -> dict:
        """Get statistics about the current databases."""
        processing_stats = self.get_processing_progress()
        return {
            "total_embeddings": self.embedding_repository.get_embedding_count(),
            "collection_name": self.embedding_repository.collection_name,
            "database_path": self.embedding_repository.db_path,
            "track_database_stats": processing_stats
        }

    def get_track_by_id(self, track_id: str) -> Optional[Track]:
        """Get track information by Plex rating key."""
        # Try database first (faster)
        stored_track = self.track_database.get_track_by_id(media_server_rating_key=track_id)
        if stored_track:
            return stored_track.to_track()

        # Fallback to media server API
        return self.media_server_repository.get_track_by_id(track_id)

    def get_all_tracks(self, limit: Optional[int] = None, offset: int = 0) -> List[Track]:
        """Get all tracks from the database with optional pagination."""
        stored_tracks = self.track_database.get_all_tracks(limit=limit, offset=offset)
        return [stored_track.to_track() for stored_track in stored_tracks]

    def search_tracks_in_database(self, search_query: str, limit: Optional[int] = None, offset: int = 0) -> List[Track]:
        """Search tracks in the database by artist, album, or title."""
        stored_tracks = self.track_database.search_tracks(search_query, limit=limit, offset=offset)
        return [stored_track.to_track() for stored_track in stored_tracks]

    def count_tracks_in_database(self, search_query: str) -> int:
        """Count tracks matching search query in the database."""
        return self.track_database.count_search_tracks(search_query)

    def search_tracks_advanced(
            self,
            artist: Optional[str] = None,
            album: Optional[str] = None,
            title: Optional[str] = None,
            limit: Optional[int] = None,
            offset: int = 0
    ) -> List[Track]:
        """Search tracks in the database using advanced criteria with AND logic."""
        stored_tracks = self.track_database.search_tracks_advanced(
            artist=artist, album=album, title=title, limit=limit, offset=offset
        )
        return [stored_track.to_track() for stored_track in stored_tracks]

    def count_tracks_advanced(
            self,
            artist: Optional[str] = None,
            album: Optional[str] = None,
            title: Optional[str] = None
    ) -> int:
        """Count tracks matching advanced search criteria in the database."""
        return self.track_database.count_search_tracks_advanced(artist=artist, album=album, title=title)

    def has_embedding(self, track_id: str) -> bool:
        """Check if embedding exists for a track."""
        return self.embedding_repository.has_embedding(track_id)

    def save_embedding(self, track_id: str, embedding: List[float]) -> None:
        """Save an embedding for a track."""
        # Get track info first
        track = self.get_track_by_id(track_id=track_id)
        if track:
            track_embedding = TrackEmbedding(
                track=track,
                embedding=embedding,
                model_id=self._config.clap.model_id
            )
            self.embedding_repository.save_embedding(track_embedding)
            # Also mark as processed in track database
            self.track_database.mark_track_processed(media_server_rating_key=track_id,
                                                     model_id=self._config.clap.model_id)

    def compute_single_embedding(self, audio_filepath: str) -> List[float]:
        """Compute embedding for a single audio file."""
        return self.embedding_generator.generate_embedding(Path(audio_filepath))

    def initialize_worker_processing(self, job_queue_service, api_host: str = "localhost", api_port: int = 8000):
        """Initialize worker-based processing use case."""
        self.worker_processing = WorkerBasedProcessingUseCase(
            job_queue_service,
            self.track_database,
            api_host,
            api_port
        )

    def can_use_workers(self) -> bool:
        """Check if workers are available for processing."""
        if not hasattr(self, 'worker_processing'):
            return False
        return self.worker_processing.can_use_workers()

    def get_worker_info(self) -> Dict[str, Any]:
        """Get information about available workers."""
        if not hasattr(self, 'worker_processing'):
            return {"active_workers": 0, "worker_details": [], "queue_stats": {}}
        return self.worker_processing.get_worker_info()

    def create_worker_tasks(self, max_tracks: Optional[int] = None) -> Dict[str, Any]:
        """Create tasks for worker processing."""
        if not hasattr(self, 'worker_processing'):
            return {
                "success": False,
                "message": "Worker processing not initialized",
                "tasks_created": 0
            }
        return self.worker_processing.create_worker_tasks(max_tracks=max_tracks, model_id=self._config.clap.model_id)

    def stop_worker_processing(self) -> Dict[str, Any]:
        """Stop worker processing by clearing pending tasks."""
        if not hasattr(self, 'worker_processing'):
            return {"cleared_tasks": 0, "message": "Worker processing not initialized"}

        # Clear pending tasks from the job queue
        cleared_count = self.worker_processing.job_queue.clear_pending_tasks()

        return {
            "cleared_tasks": cleared_count,
            "message": f"Cleared {cleared_count} pending tasks. Tasks currently being processed by workers will complete."
        }

    def has_active_worker_processing(self) -> bool:
        """Check if there are active worker processing tasks."""
        if not hasattr(self, 'worker_processing'):
            return False
        return self.worker_processing.job_queue.has_active_processing()

    def cleanup_stale_worker_tasks(self) -> int:
        """Clean up stale worker tasks and return count of cleaned tasks."""
        if not hasattr(self, 'worker_processing'):
            return 0
        return self.worker_processing.job_queue.cleanup_stale_tasks()

    def create_playlist(self, name: str, track_ids: List[str], batch_size: int = 100) -> "Playlist":
        """Create a playlist from a list of track IDs.
        
        Args:
            name: Name of the playlist
            track_ids: List of track IDs to include in the playlist
            batch_size: Number of tracks to add per batch for large playlists (default: 100)
        """
        try:
            # Get tracks by their IDs
            tracks = []
            for track_id in track_ids:
                track = self.get_track_by_id(track_id=track_id)
                if track:
                    tracks.append(track)
                else:
                    self.logger.warning(f"Track with ID {track_id} not found, skipping")

            if not tracks:
                raise ValueError("No valid tracks found for playlist creation")

            # Create playlist object
            playlist = Playlist(name=name, tracks=tracks)

            # Create playlist on the media server with batching
            created_playlist = self.media_server_repository.create_playlist(playlist, batch_size=batch_size)

            self.logger.info(f"Successfully created playlist '{name}' with {len(tracks)} tracks")
            return created_playlist

        except Exception as e:
            self.logger.error(f"Failed to create playlist '{name}': {e}", exc_info=True)
            raise

    def cleanup(self) -> None:
        """Clean up resources, including unloading the CLAP model."""
        try:
            self.logger.info("Cleaning up MyceliumService resources...")
            if hasattr(self, 'embedding_generator') and self.embedding_generator:
                self.embedding_generator.unload_model()
            self.logger.info("MyceliumService cleanup completed successfully")
        except Exception as e:
            self.logger.error(f"Error during MyceliumService cleanup: {e}", exc_info=True)

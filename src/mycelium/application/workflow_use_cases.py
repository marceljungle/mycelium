"""New use cases for separated scanning and processing workflow."""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from .job_queue import JobQueueService
from ..domain.models import TrackEmbedding
from ..domain.repositories import PlexRepository, EmbeddingRepository, EmbeddingGenerator
from ..domain.worker import ContextType
from ..infrastructure.track_database import TrackDatabase

logger = logging.getLogger(__name__)


class SeparatedLibraryScanUseCase:
    """Use case for scanning and storing track metadata."""

    def __init__(self, plex_repository: PlexRepository, track_database: TrackDatabase):
        self.plex_repository = plex_repository
        self.track_database = track_database

    def execute(self, progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """Scan the Plex music library and store track metadata."""
        logger.info("Starting library scan...")

        # Start scan session
        session_id = self.track_database.start_scan_session()

        try:
            # Get all tracks from Plex
            tracks = self.plex_repository.get_all_tracks()
            logger.info(f"Found {len(tracks)} tracks in Plex library")

            if progress_callback:
                progress_callback({"stage": "scanning", "current": len(tracks), "total": len(tracks)})

            # Save tracks to database
            scan_timestamp = datetime.now(timezone.utc)
            stats = self.track_database.save_tracks(tracks=tracks,
                                                    scan_timestamp=scan_timestamp)

            # Complete scan session
            self.track_database.complete_scan_session(
                session_id,
                stats["total"],
                stats["new"],
                stats["updated"]
            )

            result = {
                "session_id": session_id,
                "total_tracks": stats["total"],
                "new_tracks": stats["new"],
                "updated_tracks": stats["updated"],
                "scan_timestamp": scan_timestamp.isoformat()
            }

            logger.info(f"Scan completed: {stats['total']} total, {stats['new']} new, {stats['updated']} updated")

            if progress_callback:
                progress_callback({"stage": "complete", "result": result})

            return result

        except Exception as e:
            logger.error(f"Scan failed: {e}")
            raise


class ResumableEmbeddingProcessingUseCase:
    """Use case for resumable embedding processing from stored tracks."""

    def __init__(
            self,
            embedding_generator: EmbeddingGenerator,
            embedding_repository: EmbeddingRepository,
            track_database: TrackDatabase,
            model_id: str
    ):
        self.embedding_generator = embedding_generator
        self.embedding_repository = embedding_repository
        self.track_database = track_database
        self.model_id = model_id
        self._should_stop = False

    def process_embeddings(
            self,
            progress_callback: Optional[callable] = None,
            max_tracks: Optional[int] = None,
            batch_size: int = 50
    ) -> Dict[str, Any]:
        """Process embeddings for unprocessed tracks with resumability."""
        logger.info(f"Starting embedding processing with model: {self.model_id}")

        # Get unprocessed tracks for this specific model
        unprocessed_tracks = self.track_database.get_unprocessed_tracks(model_id=self.model_id,
                                                                        limit=max_tracks)

        if not unprocessed_tracks:
            logger.info("No unprocessed tracks found")
            return {
                "processed": 0,
                "failed": 0,
                "total": 0,
                "message": "No tracks to process"
            }

        logger.info(f"Found {len(unprocessed_tracks)} unprocessed tracks")

        # Start processing session
        session_id = self.track_database.start_processing_session(total_tracks=len(unprocessed_tracks),
                                                                  model_id=self.model_id)

        processed_count = 0
        failed_count = 0

        try:
            for i in range(0, len(unprocessed_tracks), batch_size):
                if self._should_stop:
                    logger.info("Processing stopped by user request")
                    break
                
                batch = unprocessed_tracks[i:i + batch_size]
                tracks = []
                filepaths = []
                valid_stored_tracks = []
                
                # Prepare batch data
                for stored_track in batch:
                    try:
                        track = stored_track.to_track()
                        tracks.append(track)
                        filepaths.append(track.filepath)
                        valid_stored_tracks.append(stored_track)
                    except Exception as e:
                        logger.error(f"Error converting track {stored_track.media_server_rating_key}: {e}")
                        failed_count += 1
                
                if not filepaths:
                    continue
                
                # Generate embeddings in batch
                embeddings = self.embedding_generator.generate_embedding_batch(filepaths)
                
                # Process results
                for track, stored_track, embedding in zip(tracks, valid_stored_tracks, embeddings):
                    try:
                        if embedding:
                            # Create track embedding object with model info
                            track_embedding = TrackEmbedding(
                                track=track, 
                                embedding=embedding, 
                                model_id=self.model_id,
                                processed_at=datetime.now(timezone.utc)
                            )

                            # Save to vector database
                            self.embedding_repository.save_embeddings(embeddings=[track_embedding])

                            # Mark as processed in metadata database
                            self.track_database.mark_track_processed(
                                media_server_rating_key=stored_track.media_server_rating_key,
                                model_id=self.model_id
                            )

                            processed_count += 1

                            if progress_callback:
                                progress_callback({
                                    "stage": "processing",
                                    "current": processed_count + failed_count,
                                    "total": len(unprocessed_tracks),
                                    "processed": processed_count,
                                    "failed": failed_count,
                                    "current_track": track.display_name
                                })
                        else:
                            logger.warning(f"Failed to generate embedding for: {track.display_name}")
                            failed_count += 1

                    except Exception as e:
                        logger.error(f"Error processing track {stored_track.media_server_rating_key}: {e}")
                        failed_count += 1

                # Update session progress periodically
                if (processed_count + failed_count) % 10 == 0:
                    self.track_database.update_processing_session(
                        session_id, processed_count, failed_count
                    )

            # Final session update
            self.track_database.update_processing_session(session_id, processed_count, failed_count)

            if not self._should_stop:
                self.track_database.complete_processing_session(session_id)

            result = {
                "session_id": session_id,
                "processed": processed_count,
                "failed": failed_count,
                "total": len(unprocessed_tracks),
                "stopped": self._should_stop
            }

            logger.info(f"Processing completed: {processed_count} processed, {failed_count} failed")

            if progress_callback:
                progress_callback({"stage": "complete", "result": result})

            return result

        except Exception as e:
            logger.info(f"Processing failed: {e}")
            raise

    def stop(self) -> None:
        """Request to stop processing."""
        self._should_stop = True
        logger.info("Stop requested - will finish current track and stop")

    def reset_stop_flag(self) -> None:
        """Reset the stop flag for a new processing session."""
        self._should_stop = False


class ProcessingProgressUseCase:
    """Use case for tracking processing progress."""

    def __init__(self, track_database: TrackDatabase):
        self.track_database = track_database

    def get_current_stats(self, model_id: Optional[str] = None) -> Dict[str, Any]:
        """Get current processing statistics, optionally filtered by model."""
        stats = self.track_database.get_processing_stats(model_id)
        latest_session = self.track_database.get_latest_processing_session()

        return {
            "total_tracks": stats["total_tracks"],
            "processed_tracks": stats["processed_tracks"],
            "unprocessed_tracks": stats["unprocessed_tracks"],
            "progress_percentage": (stats["processed_tracks"] / stats["total_tracks"] * 100) if stats[
                                                                                                    "total_tracks"] > 0 else 0,
            "model_id": model_id,
            "latest_session": latest_session
        }


class WorkerBasedProcessingUseCase:
    """Use case for processing embeddings using client workers."""

    def __init__(
            self,
            job_queue_service: JobQueueService,
            track_database: TrackDatabase,
            api_host: str = "localhost",
            api_port: int = 8000
    ):
        self.job_queue = job_queue_service
        self.track_database = track_database
        self.api_host = api_host
        self.api_port = api_port

    def can_use_workers(self) -> bool:
        """Check if there are active workers available."""
        active_workers = self.job_queue.get_active_workers()
        return len(active_workers) > 0

    def get_worker_info(self) -> Dict[str, Any]:
        """Get information about available workers."""
        active_workers = self.job_queue.get_active_workers()
        queue_stats = self.job_queue.get_queue_stats()

        return {
            "active_workers": len(active_workers),
            "worker_details": [
                {
                    "id": worker.id,
                    "ip_address": worker.ip_address,
                    "last_heartbeat": worker.last_heartbeat.isoformat()
                }
                for worker in active_workers
            ],
            "queue_stats": queue_stats
        }

    def create_worker_tasks(self, model_id: str, max_tracks: Optional[int] = None) -> Dict[str, Any]:
        """Create tasks for all unprocessed tracks to be handled by workers."""
        if not self.can_use_workers():
            return {
                "success": False,
                "message": "No active workers available",
                "tasks_created": 0
            }

        # Get unprocessed tracks
        unprocessed_tracks = self.track_database.get_unprocessed_tracks(limit=max_tracks, model_id=model_id)

        if not unprocessed_tracks:
            return {
                "success": True,
                "message": "No tracks to process",
                "tasks_created": 0
            }

        # Create tasks for each track
        tasks_created = 0
        for stored_track in unprocessed_tracks:
            try:
                download_url = f"/download_track/{stored_track.media_server_rating_key}"
                self.job_queue.create_task(stored_track.media_server_rating_key, download_url, prioritize=False,
                                           context_type=ContextType.AUDIO_PROCESSING)
                tasks_created += 1
            except Exception as e:
                logger.error(f"Failed to create task for track {stored_track.media_server_rating_key}: {e}")
                continue

        return {
            "success": True,
            "message": f"Created {tasks_created} tasks for worker processing",
            "tasks_created": tasks_created,
            "total_unprocessed": len(unprocessed_tracks),
            "worker_info": self.get_worker_info()
        }

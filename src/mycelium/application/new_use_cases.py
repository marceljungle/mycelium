"""New use cases for separated scanning and processing workflow."""

from typing import List, Optional, Dict, Any, Iterator
from datetime import datetime
from tqdm import tqdm

from ..domain.models import Track, TrackEmbedding
from ..domain.repositories import PlexRepository, EmbeddingRepository, EmbeddingGenerator
from ..infrastructure.track_database import TrackDatabase, StoredTrack


class SeparatedLibraryScanUseCase:
    """Use case for scanning and storing track metadata."""
    
    def __init__(self, plex_repository: PlexRepository, track_database: TrackDatabase):
        self.plex_repository = plex_repository
        self.track_database = track_database
    
    def execute(self, progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """Scan the Plex music library and store track metadata."""
        print("Starting library scan...")
        
        # Start scan session
        session_id = self.track_database.start_scan_session()
        
        try:
            # Get all tracks from Plex
            tracks = self.plex_repository.get_all_tracks()
            print(f"Found {len(tracks)} tracks in Plex library")
            
            if progress_callback:
                progress_callback({"stage": "scanning", "current": len(tracks), "total": len(tracks)})
            
            # Save tracks to database
            scan_timestamp = datetime.utcnow()
            stats = self.track_database.save_tracks(tracks, scan_timestamp)
            
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
            
            print(f"Scan completed: {stats['total']} total, {stats['new']} new, {stats['updated']} updated")
            
            if progress_callback:
                progress_callback({"stage": "complete", "result": result})
            
            return result
            
        except Exception as e:
            print(f"Scan failed: {e}")
            raise


class ResumableEmbeddingProcessingUseCase:
    """Use case for resumable embedding processing from stored tracks."""
    
    def __init__(
        self, 
        embedding_generator: EmbeddingGenerator,
        embedding_repository: EmbeddingRepository,
        track_database: TrackDatabase,
        batch_size: int = 16
    ):
        self.embedding_generator = embedding_generator
        self.embedding_repository = embedding_repository
        self.track_database = track_database
        self.batch_size = batch_size
        self._should_stop = False
    
    def execute(
        self, 
        progress_callback: Optional[callable] = None,
        max_tracks: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process embeddings for unprocessed tracks with resumability."""
        print("Starting embedding processing...")
        
        # Get unprocessed tracks
        unprocessed_tracks = self.track_database.get_unprocessed_tracks(limit=max_tracks)
        
        if not unprocessed_tracks:
            print("No unprocessed tracks found")
            return {
                "processed": 0,
                "failed": 0,
                "total": 0,
                "message": "No tracks to process"
            }
        
        print(f"Found {len(unprocessed_tracks)} unprocessed tracks")
        
        # Start processing session
        session_id = self.track_database.start_processing_session(len(unprocessed_tracks))
        
        processed_count = 0
        failed_count = 0
        
        try:
            # Process tracks with progress bar
            for i, stored_track in enumerate(tqdm(unprocessed_tracks, desc="Processing embeddings")):
                if self._should_stop:
                    print("Processing stopped by user request")
                    break
                
                try:
                    # Convert to domain model
                    track = stored_track.to_track()
                    
                    # Generate embedding
                    embedding = self.embedding_generator.generate_embedding(track.filepath)
                    
                    if embedding:
                        # Create track embedding object
                        track_embedding = TrackEmbedding(track=track, embedding=embedding)
                        
                        # Save to vector database
                        self.embedding_repository.save_embeddings([track_embedding])
                        
                        # Mark as processed in metadata database
                        self.track_database.mark_track_processed(stored_track.plex_rating_key)
                        
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
                        print(f"Failed to generate embedding for: {track.display_name}")
                        failed_count += 1
                        
                except Exception as e:
                    print(f"Error processing track {stored_track.plex_rating_key}: {e}")
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
            
            print(f"Processing completed: {processed_count} processed, {failed_count} failed")
            
            if progress_callback:
                progress_callback({"stage": "complete", "result": result})
            
            return result
            
        except Exception as e:
            print(f"Processing failed: {e}")
            raise
    
    def stop(self) -> None:
        """Request to stop processing."""
        self._should_stop = True
        print("Stop requested - will finish current track and stop")
    
    def reset_stop_flag(self) -> None:
        """Reset the stop flag for a new processing session."""
        self._should_stop = False


class ProcessingProgressUseCase:
    """Use case for tracking processing progress."""
    
    def __init__(self, track_database: TrackDatabase):
        self.track_database = track_database
    
    def get_current_stats(self) -> Dict[str, Any]:
        """Get current processing statistics."""
        stats = self.track_database.get_processing_stats()
        latest_session = self.track_database.get_latest_processing_session()
        
        return {
            "total_tracks": stats["total_tracks"],
            "processed_tracks": stats["processed_tracks"],
            "unprocessed_tracks": stats["unprocessed_tracks"],
            "progress_percentage": (stats["processed_tracks"] / stats["total_tracks"] * 100) if stats["total_tracks"] > 0 else 0,
            "latest_session": latest_session
        }
    
    def can_resume_processing(self) -> bool:
        """Check if there's a resumable processing session."""
        latest_session = self.track_database.get_latest_processing_session()
        return (latest_session and 
                latest_session.get("is_resumable", False) and 
                latest_session.get("completed_at") is None)


class DatabaseMaintenanceUseCase:
    """Use case for database maintenance operations."""
    
    def __init__(self, track_database: TrackDatabase):
        self.track_database = track_database
    
    def cleanup_old_tracks(self, days_old: int = 30) -> int:
        """Remove tracks that haven't been scanned in specified days."""
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        return self.track_database.cleanup_old_tracks(cutoff_date)
    
    def reset_processing_state(self) -> int:
        """Reset all tracks to unprocessed state (for reprocessing)."""
        # This would require additional database methods
        pass
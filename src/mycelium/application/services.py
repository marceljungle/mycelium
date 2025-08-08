"""Application services for orchestrating business logic."""

from typing import List, Optional, Dict, Any
from pathlib import Path

from mycelium.domain.models import Track, TrackEmbedding, SearchResult
from mycelium.infrastructure import (
    PlexMusicRepository, 
    CLAPEmbeddingGenerator, 
    ChromaEmbeddingRepository,
    TrackDatabase
)
from mycelium.application.use_cases import (
    LibraryScanUseCase,
    EmbeddingGenerationUseCase, 
    EmbeddingIndexingUseCase,
    MusicSearchUseCase
)
from mycelium.application.new_use_cases import (
    SeparatedLibraryScanUseCase,
    ResumableEmbeddingProcessingUseCase,
    ProcessingProgressUseCase,
    DatabaseMaintenanceUseCase
)


class MyceliumService:
    """Main service for orchestrating the Mycelium application."""
    
    def __init__(
        self,
        plex_url: str = None,
        plex_token: str = None,
        music_library_name: str = "Music",
        db_path: str = "./music_vector_db",
        collection_name: str = "my_music_library",
        model_id: str = "laion/larger_clap_music_and_speech",
        track_db_path: str = "./mycelium_tracks.db"
    ):
        # Initialize repositories and adapters
        self.plex_repository = PlexMusicRepository(
            plex_url=plex_url,
            plex_token=plex_token,
            music_library_name=music_library_name
        )
        
        self.embedding_generator = CLAPEmbeddingGenerator(model_id=model_id)
        
        self.embedding_repository = ChromaEmbeddingRepository(
            db_path=db_path,
            collection_name=collection_name
        )
        
        self.track_database = TrackDatabase(track_db_path)
        
        # Initialize legacy use cases (for backward compatibility)
        self.library_scan = LibraryScanUseCase(self.plex_repository)
        self.embedding_generation = EmbeddingGenerationUseCase(self.embedding_generator)
        self.embedding_indexing = EmbeddingIndexingUseCase(self.embedding_repository)
        self.music_search = MusicSearchUseCase(
            self.embedding_repository, 
            self.embedding_generator
        )
        
        # Initialize new use cases
        self.separated_scan = SeparatedLibraryScanUseCase(
            self.plex_repository, 
            self.track_database
        )
        self.resumable_processing = ResumableEmbeddingProcessingUseCase(
            self.embedding_generator,
            self.embedding_repository,
            self.track_database
        )
        self.progress_tracker = ProcessingProgressUseCase(self.track_database)
        self.database_maintenance = DatabaseMaintenanceUseCase(self.track_database)
    
    # New separated workflow methods
    def scan_library_to_database(self, progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """Scan the Plex library and store metadata to database."""
        return self.separated_scan.execute(progress_callback)
    
    def process_embeddings_from_database(
        self, 
        progress_callback: Optional[callable] = None,
        max_tracks: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process embeddings for unprocessed tracks from database."""
        return self.resumable_processing.execute(progress_callback, max_tracks)
    
    def stop_processing(self) -> None:
        """Stop the current embedding processing."""
        self.resumable_processing.stop()
    
    def reset_processing_stop_flag(self) -> None:
        """Reset the stop flag for new processing session."""
        self.resumable_processing.reset_stop_flag()
    
    def get_processing_progress(self) -> Dict[str, Any]:
        """Get current processing progress and statistics."""
        return self.progress_tracker.get_current_stats()
    
    def can_resume_processing(self) -> bool:
        """Check if processing can be resumed."""
        return self.progress_tracker.can_resume_processing()
    
    # Legacy methods (maintained for backward compatibility)
    def scan_library(self) -> List[Track]:
        """Scan the Plex music library (legacy method)."""
        return self.library_scan.execute()
    
    def generate_embeddings(self, tracks: List[Track]) -> List[TrackEmbedding]:
        """Generate embeddings for tracks (legacy method)."""
        return self.embedding_generation.execute(tracks)
    
    def index_embeddings(self, embeddings: List[TrackEmbedding]) -> None:
        """Index embeddings in the vector database (legacy method)."""
        self.embedding_indexing.execute(embeddings)
    
    
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
        return self.music_search.search_by_track_id(track_id, n_results)
    
    # Updated full_library_processing (now separated into scan and process)
    def full_library_processing(self) -> None:
        """Complete workflow: scan library to database, then process embeddings."""
        print("Starting full library processing with separated workflow...")
        
        # Step 1: Scan library to database
        print("\n=== Scanning Plex Library to Database ===")
        scan_result = self.scan_library_to_database()
        print(f"Scan completed: {scan_result['total_tracks']} total, {scan_result['new_tracks']} new, {scan_result['updated_tracks']} updated")
        
        # Step 2: Process embeddings from database
        print("\n=== Processing Embeddings from Database ===")
        process_result = self.process_embeddings_from_database()
        print(f"Processing completed: {process_result['processed']} processed, {process_result['failed']} failed")
        
        print("\n=== Processing Complete ===")
        print(f"Total tracks in database: {scan_result['total_tracks']}")
        print(f"Embeddings processed: {process_result['processed']}")
        print(f"Embeddings in vector database: {self.embedding_repository.get_embedding_count()}")
    
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
        stored_track = self.track_database.get_track_by_id(track_id)
        if stored_track:
            return stored_track.to_track()
        
        # Fallback to Plex API
        return self.plex_repository.get_track_by_id(track_id)
    
    def has_embedding(self, track_id: str) -> bool:
        """Check if embedding exists for a track."""
        return self.embedding_repository.has_embedding(track_id)
    
    def save_embedding(self, track_id: str, embedding: List[float]) -> None:
        """Save an embedding for a track."""
        # Get track info first
        track = self.get_track_by_id(track_id)
        if track:
            track_embedding = TrackEmbedding(
                track=track,
                embedding=embedding
            )
            self.embedding_repository.save_embedding(track_embedding)
            # Also mark as processed in track database
            self.track_database.mark_track_processed(track_id)
    
    def compute_embedding_cpu(self, audio_filepath: str) -> List[float]:
        """Compute embedding on CPU (fallback)."""
        return self.embedding_generator.generate_embedding_from_file(Path(audio_filepath))
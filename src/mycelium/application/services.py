"""Application services for orchestrating business logic."""

from typing import List, Optional
from pathlib import Path

from ..domain.models import Track, TrackEmbedding, SearchResult
from ..infrastructure import PlexMusicRepository, CLAPEmbeddingGenerator, ChromaEmbeddingRepository
from .use_cases import (
    LibraryScanUseCase,
    EmbeddingGenerationUseCase, 
    EmbeddingIndexingUseCase,
    MusicSearchUseCase,
    DataExportUseCase,
    DataImportUseCase
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
        model_id: str = "laion/larger_clap_music_and_speech"
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
        
        # Initialize use cases
        self.library_scan = LibraryScanUseCase(self.plex_repository)
        self.embedding_generation = EmbeddingGenerationUseCase(self.embedding_generator)
        self.embedding_indexing = EmbeddingIndexingUseCase(self.embedding_repository)
        self.music_search = MusicSearchUseCase(
            self.embedding_repository, 
            self.embedding_generator
        )
        self.data_export = DataExportUseCase(self.plex_repository)
        self.data_import = DataImportUseCase()
    
    def scan_library(self) -> List[Track]:
        """Scan the Plex music library."""
        return self.library_scan.execute()
    
    def generate_embeddings(self, tracks: List[Track]) -> List[TrackEmbedding]:
        """Generate embeddings for tracks."""
        return self.embedding_generation.execute(tracks)
    
    def index_embeddings(self, embeddings: List[TrackEmbedding]) -> None:
        """Index embeddings in the vector database."""
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
    
    def export_library(self, output_file: str) -> None:
        """Export library data to JSON."""
        self.data_export.export_library_to_json(output_file)
    
    def import_embeddings(self, input_file: str) -> List[TrackEmbedding]:
        """Import embeddings from JSON."""
        return self.data_import.import_embeddings_from_json(input_file)
    
    def full_library_processing(self) -> None:
        """Complete workflow: scan library, generate embeddings, and index them."""
        print("Starting full library processing...")
        
        # Step 1: Scan library
        print("\n=== Scanning Plex Library ===")
        tracks = self.scan_library()
        print(f"Found {len(tracks)} tracks")
        
        # Step 2: Generate embeddings
        print("\n=== Generating Embeddings ===")
        embeddings = self.generate_embeddings(tracks)
        print(f"Generated {len(embeddings)} embeddings")
        
        # Step 3: Index embeddings
        print("\n=== Indexing Embeddings ===")
        self.index_embeddings(embeddings)
        
        print("\n=== Processing Complete ===")
        print(f"Total tracks processed: {len(embeddings)}")
        print(f"Embeddings in database: {self.embedding_repository.get_embedding_count()}")
    
    def get_database_stats(self) -> dict:
        """Get statistics about the current database."""
        return {
            "total_embeddings": self.embedding_repository.get_embedding_count(),
            "collection_name": self.embedding_repository.collection_name,
            "database_path": self.embedding_repository.db_path
        }
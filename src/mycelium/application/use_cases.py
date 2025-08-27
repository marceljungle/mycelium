"""Use cases for the Mycelium application."""

import logging
from pathlib import Path
from typing import List

from ..domain.models import SearchResult, MediaServerType, Track
from ..domain.repositories import EmbeddingRepository, EmbeddingGenerator

class MusicSearchUseCase:
    """Use case for searching music by similarity."""
    
    def __init__(
        self, 
        embedding_repository: EmbeddingRepository,
        embedding_generator: EmbeddingGenerator
    ):
        self.embedding_repository = embedding_repository
        self.embedding_generator = embedding_generator
        self.logger = logging.getLogger(__name__)
    
    def search_by_audio_file(
        self, 
        filepath: Path, 
        n_results: int = 10,
        exclude_self: bool = True
    ) -> List[SearchResult]:
        """Find similar songs to an audio file."""
        self.logger.info(f"Searching for songs similar to: {filepath.name}")
        
        # Generate embedding for the query audio
        query_embedding = self.embedding_generator.generate_embedding(filepath)
        
        if query_embedding is None:
            self.logger.error("Could not generate embedding for the query.")
            return []
        
        # Search in the database
        # Request n_results + 1 to account for potentially discarding the same song
        results = self.embedding_repository.search_by_embedding(
            query_embedding, 
            n_results=n_results + 1 if exclude_self else n_results
        )
        
        # Filter out the same file if requested
        if exclude_self:
            results = [
                result for result in results 
                if result.track.filepath != filepath
            ][:n_results]
        
        return results
    
    def search_by_text(self, query_text: str, n_results: int = 10) -> List[SearchResult]:
        """Find songs that match a text description."""
        self.logger.info(f"Searching for songs matching: '{query_text}'")
        
        # Generate embedding for the text query
        text_embedding = self.embedding_generator.generate_text_embedding(query_text)
        
        if text_embedding is None:
            self.logger.error("Could not generate embedding for the text query.")
            return []
        
        # Search in the database
        results = self.embedding_repository.search_by_embedding(text_embedding, n_results)
        
        return results
    
    def search_by_track_id(self, track_id: str, n_results: int = 10) -> List[SearchResult]:
        """Find songs similar to a track identified by its ID."""
        self.logger.info(f"Searching for songs similar to track ID: {track_id}")
        
        # Get the embedding for this track
        embedding = self.embedding_repository.get_embedding_by_track_id(track_id)
        
        if embedding is None:
            self.logger.error(f"No embedding found for track ID: {track_id}")
            # Try to check if the embedding exists using has_embedding
            has_emb = self.embedding_repository.has_embedding(track_id)
            self.logger.error(f"Double-check has_embedding for track {track_id}: {has_emb}")
            return []
        
        self.logger.info(f"Found embedding for track {track_id}, size: {len(embedding)}")
        
        # Search for similar tracks
        results = self.embedding_repository.search_by_embedding(embedding, n_results + 1)
        
        # Filter out the same track (it will be the first result with distance 0)
        results = [
            result for result in results 
            if result.track.media_server_rating_key != track_id
        ][:n_results]
        
        self.logger.info(f"Found {len(results)} similar tracks for track {track_id}")
        return results
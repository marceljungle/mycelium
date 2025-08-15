"""Use cases for the Mycelium application."""

import logging
from pathlib import Path
from typing import List

from ..domain.models import Track, TrackEmbedding, SearchResult
from ..domain.repositories import PlexRepository, EmbeddingRepository, EmbeddingGenerator


class LibraryScanUseCase:
    """Use case for scanning the Plex music library."""
    
    def __init__(self, plex_repository: PlexRepository):
        self.plex_repository = plex_repository
    
    def execute(self) -> List[Track]:
        """Scan the Plex music library and return all tracks."""
        return self.plex_repository.get_all_tracks()


class EmbeddingGenerationUseCase:
    """Use case for generating embeddings for tracks."""
    
    def __init__(
        self, 
        embedding_generator: EmbeddingGenerator,
        batch_size: int = 16
    ):
        self.embedding_generator = embedding_generator
        self.batch_size = batch_size
        self.logger = logging.getLogger(__name__)
    
    def execute(self, tracks: List[Track]) -> List[TrackEmbedding]:
        """Generate embeddings for a list of tracks."""
        track_embeddings = []
        
        self.logger.info(f"Generating embeddings for {len(tracks)} tracks...")
        
        for i in range(0, len(tracks), self.batch_size):
            batch_tracks = tracks[i:i + self.batch_size]
            
            for track in batch_tracks:
                embedding = self.embedding_generator.generate_embedding(track.filepath)
                if embedding:
                    track_embeddings.append(TrackEmbedding(track=track, embedding=embedding))
                else:
                    self.logger.warning(f"Failed to generate embedding for: {track.display_name}")
            
            # Periodic progress update
            if i % (self.batch_size * 10) == 0 and i > 0:
                self.logger.info(f"Processed {len(track_embeddings)} tracks so far...")
        
        self.logger.info(f"Generated embeddings for {len(track_embeddings)} tracks")
        return track_embeddings


class EmbeddingIndexingUseCase:
    """Use case for indexing embeddings in the vector database."""
    
    def __init__(self, embedding_repository: EmbeddingRepository):
        self.embedding_repository = embedding_repository
    
    def execute(self, embeddings: List[TrackEmbedding]) -> None:
        """Index embeddings in the vector database."""
        self.embedding_repository.save_embeddings(embeddings)


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
            return []
        
        # Search for similar tracks
        results = self.embedding_repository.search_by_embedding(embedding, n_results + 1)
        
        # Filter out the same track (it will be the first result with distance 0)
        results = [
            result for result in results 
            if result.track.plex_rating_key != track_id
        ][:n_results]
        
        return results
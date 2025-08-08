"""ChromaDB integration for storing and searching embeddings."""

from typing import List, Optional
from pathlib import Path

import chromadb
from tqdm import tqdm

from ..domain.models import Track, TrackEmbedding, SearchResult
from ..domain.repositories import EmbeddingRepository


class ChromaEmbeddingRepository(EmbeddingRepository):
    """Implementation of EmbeddingRepository using ChromaDB."""
    
    def __init__(
        self,
        db_path: str = "./music_vector_db",
        collection_name: str = "my_music_library",
        batch_size: int = 1000
    ):
        self.db_path = db_path
        self.collection_name = collection_name
        self.batch_size = batch_size
        
        # Initialize ChromaDB client and collection
        self.client = chromadb.PersistentClient(path=db_path)
        
        # Use 'get_or_create_collection' for idempotency
        # Specify 'cosine' distance metric for normalized embeddings
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        print(f"Collection '{collection_name}' ready. Current elements: {self.collection.count()}")
    
    def save_embeddings(self, embeddings: List[TrackEmbedding]) -> None:
        """Save track embeddings to ChromaDB."""
        if not embeddings:
            return
        
        # Prepare data for batch insertion
        ids = []
        embedding_vectors = []
        metadatas = []

        for track_embedding in embeddings:
            track = track_embedding.track
            ids.append(track.plex_rating_key)
            embedding_vectors.append(track_embedding.embedding)
            metadatas.append({
                "filepath": str(track.filepath),
                "artist": track.artist,
                "album": track.album,
                "title": track.title
            })

        # Insert in batches for maximum efficiency
        for i in tqdm(range(0, len(ids), self.batch_size), desc="Indexing in ChromaDB"):
            end_idx = min(i + self.batch_size, len(ids))
            id_batch = ids[i:end_idx]
            embedding_batch = embedding_vectors[i:end_idx]
            metadata_batch = metadatas[i:end_idx]

            self.collection.add(
                ids=id_batch,
                embeddings=embedding_batch,
                metadatas=metadata_batch
            )

        print("Indexing completed!")
        print(f"Total elements in collection '{self.collection_name}': {self.collection.count()}")
    
    def search_by_embedding(self, embedding: List[float], n_results: int = 10) -> List[SearchResult]:
        """Search for similar tracks by embedding."""
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results
        )
        
        return self._parse_search_results(results)
    
    def search_by_text(self, query: str, n_results: int = 10) -> List[SearchResult]:
        """Search for tracks by text description."""
        # This method would need the CLAP model to generate text embeddings
        # For now, it's a placeholder that would be implemented in the service layer
        raise NotImplementedError("Text search should be implemented in the service layer")
    
    def get_embedding_count(self) -> int:
        """Get the total number of embeddings stored."""
        return self.collection.count()
    
    def _parse_search_results(self, results: dict) -> List[SearchResult]:
        """Parse ChromaDB results into SearchResult objects."""
        search_results = []
        
        if not results['ids'] or not results['ids'][0]:
            return search_results
        
        for i in range(len(results['ids'][0])):
            metadata = results['metadatas'][0][i]
            distance = results['distances'][0][i]
            
            track = Track(
                artist=metadata['artist'],
                album=metadata['album'],
                title=metadata['title'],
                filepath=Path(metadata['filepath']),
                plex_rating_key=results['ids'][0][i]
            )
            
            # Convert distance to similarity score (1 - distance for cosine)
            similarity_score = 1.0 - distance
            
            search_results.append(SearchResult(
                track=track,
                similarity_score=similarity_score,
                distance=distance
            ))
        
        return search_results
    
    def has_embedding(self, track_id: str) -> bool:
        """Check if an embedding exists for a track."""
        try:
            result = self.collection.get(ids=[track_id])
            return len(result['ids']) > 0
        except Exception:
            return False
    
    def save_embedding(self, track_embedding: TrackEmbedding) -> None:
        """Save a single track embedding to ChromaDB."""
        track = track_embedding.track
        
        self.collection.add(
            ids=[track.plex_rating_key],
            embeddings=[track_embedding.embedding],
            metadatas=[{
                "filepath": str(track.filepath),
                "artist": track.artist,
                "album": track.album,
                "title": track.title
            }]
        )
    
    def get_embedding_by_track_id(self, track_id: str) -> Optional[List[float]]:
        """Get embedding for a specific track."""
        try:
            result = self.collection.get(
                ids=[track_id],
                include=['embeddings']
            )
            if result['embeddings'] and len(result['embeddings']) > 0:
                return result['embeddings'][0]
            return None
        except Exception:
            return None
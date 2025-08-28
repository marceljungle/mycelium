"""ChromaDB integration for storing and searching embeddings."""

import logging
import re
from pathlib import Path
from typing import List, Optional

import chromadb
from tqdm import tqdm

from ..domain.models import Track, TrackEmbedding, SearchResult, MediaServerType
from ..domain.repositories import EmbeddingRepository

logger = logging.getLogger(__name__)


class ChromaEmbeddingRepository(EmbeddingRepository):
    """Implementation of EmbeddingRepository using ChromaDB with model-specific collections."""

    def __init__(
            self,
            db_path: str,
            media_server_type: MediaServerType,
            collection_name: str = "my_music_library",
            model_id: str = "laion/larger_clap_music_and_speech",
            batch_size: int = 1000,
    ):
        self.db_path = db_path
        self.base_collection_name = collection_name
        self.model_id = model_id
        self.batch_size = batch_size
        self.media_server_type = media_server_type

        # Initialize ChromaDB client
        try:
            Path(db_path).mkdir(parents=True, exist_ok=True)
        except Exception:
            logger.error(f"Failed to create database directory at {db_path}. Please check permissions.")
        self.client = chromadb.PersistentClient(path=db_path)

        # Create model-specific collection name
        self.collection_name = self._get_collection_name_for_model(model_id)

        # Specify 'cosine' distance metric for normalized embeddings
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine", "model_id": model_id}
        )

        logger.info(
            f"Collection '{self.collection_name}' ready for model '{model_id}'. Current elements: {self.collection.count()}")

    def _get_collection_name_for_model(self, model_id: str) -> str:
        """Generate a safe collection name for the given model ID."""
        # Make model ID safe for collection name (alphanumeric and underscores only)
        safe_model_id = re.sub(r'\W', '_', model_id.replace('/', '_'))
        return f"{self.base_collection_name}_{safe_model_id}"

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
            ids.append(track.unique_id)
            embedding_vectors.append(track_embedding.embedding)
            metadatas.append({
                "filepath": str(track.filepath),
                "artist": track.artist,
                "album": track.album,
                "title": track.title,
                "media_server_type": track.media_server_type.value,
                "media_server_rating_key": track.media_server_rating_key,
                "model_id": self.model_id
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

        logger.info("Indexing completed!")
        logger.info(f"Total elements in collection '{self.collection_name}': {self.collection.count()}")

    def search_by_embedding(self, embedding: List[float], n_results: int = 10) -> List[SearchResult]:
        """Search for similar tracks by embedding."""
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results
        )

        return self._parse_search_results(results.copy())

    def get_embedding_count(self) -> int:
        """Get the total number of embeddings stored."""
        return self.collection.count()

    @staticmethod
    def _parse_search_results(results: dict) -> List[SearchResult]:
        """Parse ChromaDB results into SearchResult objects."""
        search_results = []

        if not results['ids'] or not results['ids'][0]:
            return search_results

        for i in range(len(results['ids'][0])):
            metadata = results['metadatas'][0][i]
            distance = results['distances'][0][i]
            unique_id = results['ids'][0][i]

            # Parse unique_id to get media server info
            media_server_type_str, media_server_rating_key = unique_id.split(':', 1)

            from ..domain.models import MediaServerType
            try:
                media_server_type = MediaServerType(media_server_type_str)
            except ValueError:
                media_server_type = MediaServerType.PLEX  # Default fallback

            track = Track(
                artist=metadata['artist'],
                album=metadata['album'],
                title=metadata['title'],
                filepath=Path(metadata['filepath']),
                media_server_rating_key=media_server_rating_key,
                media_server_type=media_server_type
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
        track_id = Track(media_server_type=self.media_server_type,
              media_server_rating_key=track_id).unique_id
        logger.debug(
            f"Checking embedding for track {track_id}: collection_name={self.collection_name}, model_id={self.model_id}"
        )
        try:
            result = self.collection.get(ids=[track_id])
            exists = len(result['ids']) > 0
            logger.debug(f"Checking embedding for track {track_id}: exists={exists}")
            return exists
        except Exception as e:
            logger.error(f"Error checking embedding for track {track_id}: {e}")
            return False

    def save_embedding(self, track_embedding: TrackEmbedding) -> None:
        """Save a single track embedding to ChromaDB."""
        track = track_embedding.track
        track_id = track.unique_id

        logger.info(f"Saving embedding to ChromaDB for track {track_id}: {track.artist} - {track.title}")
        logger.info(f"Collection count before save: {self.collection.count()}")

        # Check if embedding already exists, if so, update it
        existing = self.collection.get(ids=[track_id])
        if existing['ids']:
            logger.info(f"Updating existing embedding for track {track_id}")
            self.collection.update(
                ids=[track_id],
                embeddings=[track_embedding.embedding],
                metadatas=[{
                    "filepath": str(track.filepath),
                    "artist": track.artist,
                    "album": track.album,
                    "title": track.title,
                    "media_server_type": track.media_server_type.value,
                    "media_server_rating_key": track.media_server_rating_key,
                    "model_id": self.model_id
                }]
            )
        else:
            logger.info(f"Adding new embedding for track {track_id}")
            self.collection.add(
                ids=[track_id],
                embeddings=[track_embedding.embedding],
                metadatas=[{
                    "filepath": str(track.filepath),
                    "artist": track.artist,
                    "album": track.album,
                    "title": track.title,
                    "media_server_type": track.media_server_type.value,
                    "media_server_rating_key": track.media_server_rating_key,
                    "model_id": self.model_id
                }]
            )

        logger.info(f"Collection count after save: {self.collection.count()}")
        logger.info(f"Successfully saved embedding to ChromaDB for track {track_id}")

    def get_embedding_by_track_id(self, track_id: str) -> Optional[List[float]]:
        """Get embedding for a specific track."""
        track_id = Track(media_server_type=self.media_server_type, media_server_rating_key=track_id).unique_id
        try:
            result = self.collection.get(
                ids=[track_id],
                include=['embeddings']
            )
            if result['embeddings'] is not None and len(result['embeddings']) > 0:
                embedding = result['embeddings'][0]
                logger.debug(
                    f"Retrieved embedding for track {track_id}, size: {len(embedding) if embedding is not None else 0}")
                return embedding
            else:
                logger.debug(f"No embedding found in ChromaDB for track {track_id}")
                return None
        except Exception as e:
            logger.error(f"Error retrieving embedding for track {track_id}: {e}")
            return None

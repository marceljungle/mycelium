"""SQLite database for storing track metadata and processing state."""

import sqlite3
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..domain.models import Track, MediaServerType
from ..config import get_user_data_dir


@dataclass
class StoredTrack:
    """Track with additional metadata for database storage."""
    media_server_rating_key: str
    media_server_type: str
    artist: str
    album: str
    title: str
    filepath: str
    added_at: datetime
    last_scanned: datetime
    
    def to_track(self) -> Track:
        """Convert to domain Track model."""
        return Track(
            artist=self.artist,
            album=self.album,
            title=self.title,
            filepath=Path(self.filepath),
            media_server_rating_key=self.media_server_rating_key,
            media_server_type=MediaServerType(self.media_server_type)
        )
    
    @classmethod
    def from_track(cls, track: Track, added_at: datetime = None) -> "StoredTrack":
        """Create StoredTrack from domain Track model."""
        now = datetime.now(timezone.utc)
        return cls(
            media_server_rating_key=track.media_server_rating_key,
            media_server_type=track.media_server_type.value,
            artist=track.artist,
            album=track.album,
            title=track.title,
            filepath=str(track.filepath),
            added_at=added_at or now,
            last_scanned=now
        )


@dataclass
class TrackEmbeddingRecord:
    """Record of an embedding processed for a specific track and model."""
    id: Optional[int]
    media_server_rating_key: str
    media_server_type: str
    model_id: str
    processed_at: datetime

logger = logging.getLogger(__name__)

class TrackDatabase:
    """SQLite database for managing track metadata and processing state."""
    
    def __init__(self, db_path: Optional[str], media_server_type: MediaServerType) -> None:
        # Default to user data directory if path is not provided
        if not db_path:
            db_path = str(get_user_data_dir() / "mycelium_tracks.db")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.media_server_type = media_server_type
        logger.debug(f"Initializing TrackDatabase with path: {self.db_path}, media_server_type: {media_server_type}")
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize database tables."""
        logger.debug(f"Initializing database tables at {self.db_path}")
        with sqlite3.connect(self.db_path) as conn:
            # Create tracks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tracks (
                    media_server_rating_key TEXT NOT NULL,
                    media_server_type TEXT NOT NULL DEFAULT 'plex',
                    artist TEXT NOT NULL,
                    album TEXT NOT NULL,
                    title TEXT NOT NULL,
                    filepath TEXT NOT NULL,
                    added_at TIMESTAMP NOT NULL,
                    last_scanned TIMESTAMP NOT NULL,
                    PRIMARY KEY (media_server_rating_key, media_server_type)
                )
            """)
            
            # Create track_embeddings table for tracking processed models
            conn.execute("""
                CREATE TABLE IF NOT EXISTS track_embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    media_server_rating_key TEXT NOT NULL,
                    media_server_type TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    processed_at TIMESTAMP NOT NULL,
                    UNIQUE(media_server_rating_key, media_server_type, model_id),
                    FOREIGN KEY (media_server_rating_key, media_server_type) 
                        REFERENCES tracks(media_server_rating_key, media_server_type)
                )
            """)
            
            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_media_server ON tracks(media_server_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_scanned ON tracks(last_scanned)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_track_embeddings_lookup ON track_embeddings(media_server_rating_key, media_server_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_track_embeddings_model ON track_embeddings(model_id)")
            conn.commit()
            logger.debug("Database tables and indexes created/verified successfully")
    
    def save_tracks(self, tracks: List[Track], scan_timestamp: datetime = None) -> Dict[str, int]:
        """Save tracks to database, return statistics."""
        if scan_timestamp is None:
            scan_timestamp = datetime.now(timezone.utc)
        
        logger.debug(f"Saving {len(tracks)} tracks to database with timestamp {scan_timestamp}")
        stats = {"new": 0, "updated": 0, "total": len(tracks)}
        
        with sqlite3.connect(self.db_path) as conn:
            for i, track in enumerate(tracks):
                if i % 100 == 0 and i > 0:
                    logger.debug(f"Processing track {i}/{len(tracks)}")
                
                # Check if track exists
                existing = conn.execute(
                    "SELECT media_server_rating_key, last_scanned FROM tracks WHERE media_server_rating_key = ? AND media_server_type = ?",
                    (track.media_server_rating_key, track.media_server_type.value)
                ).fetchone()
                
                if existing:
                    # Update existing track
                    conn.execute("""
                        UPDATE tracks 
                        SET artist = ?, album = ?, title = ?, filepath = ?, last_scanned = ?
                        WHERE media_server_rating_key = ? AND media_server_type = ?
                    """, (track.artist, track.album, track.title, str(track.filepath), 
                         scan_timestamp, track.media_server_rating_key, track.media_server_type.value))
                    stats["updated"] += 1
                    logger.debug(f"Updated track: {track.artist} - {track.title}")
                else:
                    # Insert new track
                    conn.execute("""
                        INSERT INTO tracks 
                        (media_server_rating_key, media_server_type, artist, album, title, filepath, added_at, last_scanned)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (track.media_server_rating_key, track.media_server_type.value, track.artist, track.album, track.title,
                         str(track.filepath), scan_timestamp, scan_timestamp))
                    stats["new"] += 1
                    logger.debug(f"Added new track: {track.artist} - {track.title}")
            
            conn.commit()
        
        logger.debug(f"Track save operation completed: {stats}")
        return stats
    
    def get_unprocessed_tracks(self, model_id: str, limit: Optional[int] = None) -> List[StoredTrack]:
        """Get tracks that haven't been processed for embeddings with the specified model."""
        logger.debug(f"Getting unprocessed tracks for model: {model_id}, limit: {limit}")
        query = """
            SELECT t.media_server_rating_key, t.media_server_type, t.artist, t.album, t.title, 
                   t.filepath, t.added_at, t.last_scanned
            FROM tracks t
            LEFT JOIN track_embeddings te ON (
                t.media_server_rating_key = te.media_server_rating_key 
                AND t.media_server_type = te.media_server_type 
                AND te.model_id = ?
            )
            WHERE te.id IS NULL
            ORDER BY t.added_at
        """
        
        params = [model_id]
        if limit:
            query += f" LIMIT {limit}"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            
            tracks = [
                StoredTrack(
                    media_server_rating_key=row["media_server_rating_key"],
                    media_server_type=row["media_server_type"],
                    artist=row["artist"],
                    album=row["album"],
                    title=row["title"],
                    filepath=row["filepath"],
                    added_at=datetime.fromisoformat(row["added_at"]),
                    last_scanned=datetime.fromisoformat(row["last_scanned"])
                )
                for row in rows
            ]
            
        logger.debug(f"Found {len(tracks)} unprocessed tracks for model {model_id}")
        return tracks
    
    def mark_track_processed(self, media_server_rating_key: str, model_id: str, processed_at: datetime = None) -> None:
        """Mark a track as processed for embeddings with a specific model."""
        if processed_at is None:
            processed_at = datetime.now(timezone.utc)
        
        logger.debug(f"Marking track {media_server_rating_key} as processed for model {model_id}")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO track_embeddings 
                (media_server_rating_key, media_server_type, model_id, processed_at)
                VALUES (?, ?, ?, ?)
            """, (media_server_rating_key, self.media_server_type.value, model_id, processed_at))
            conn.commit()
        logger.debug(f"Track {media_server_rating_key} marked as processed for model {model_id}")
    

    
    def get_processing_stats(self, model_id: Optional[str] = None) -> Dict[str, int]:
        """Get processing statistics, optionally filtered by model."""
        logger.debug(f"Getting processing stats for model: {model_id}")
        with sqlite3.connect(self.db_path) as conn:
            stats = {}
            
            result = conn.execute("SELECT COUNT(*) as total FROM tracks").fetchone()
            stats["total_tracks"] = result[0]
            
            if model_id:
                # Get stats for specific model
                result = conn.execute("""
                    SELECT COUNT(*) as processed 
                    FROM track_embeddings 
                    WHERE model_id = ?
                """, (model_id,)).fetchone()
                stats["processed_tracks"] = result[0]
            else:
                # Get stats for any model (at least one embedding exists)
                result = conn.execute("""
                    SELECT COUNT(DISTINCT t.media_server_rating_key, t.media_server_type) as processed
                    FROM tracks t
                    INNER JOIN track_embeddings te ON (
                        t.media_server_rating_key = te.media_server_rating_key 
                        AND t.media_server_type = te.media_server_type
                    )
                """).fetchone()
                stats["processed_tracks"] = result[0]
            
            stats["unprocessed_tracks"] = stats["total_tracks"] - stats["processed_tracks"]
            
            logger.debug(f"Processing stats: {stats}")
            return stats

    def get_track_by_id(self, media_server_rating_key: str) -> Optional[StoredTrack]:
        """Get a specific track by media server rating key."""
        logger.debug(f"Getting track by ID: {media_server_rating_key}")
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("""
                SELECT media_server_rating_key, media_server_type, artist, album, title, filepath, added_at, last_scanned
                FROM tracks 
                WHERE media_server_rating_key = ? AND media_server_type = ?
            """, (media_server_rating_key, self.media_server_type.value)).fetchone()
            
            if row:
                track = StoredTrack(
                    media_server_rating_key=row["media_server_rating_key"],
                    media_server_type=row["media_server_type"],
                    artist=row["artist"],
                    album=row["album"],
                    title=row["title"],
                    filepath=row["filepath"],
                    added_at=datetime.fromisoformat(row["added_at"]),
                    last_scanned=datetime.fromisoformat(row["last_scanned"])
                )
                logger.debug(f"Found track: {track.artist} - {track.title}")
                return track
            
            logger.debug(f"Track not found: {media_server_rating_key}")
            return None
    

    
    def get_all_tracks(self, limit: Optional[int] = None, offset: int = 0) -> List[StoredTrack]:
        """Get all tracks from the database with optional pagination."""
        query = """
            SELECT media_server_rating_key, media_server_type, artist, album, title, filepath, added_at, last_scanned
            FROM tracks 
            ORDER BY artist, album, title
        """
        
        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query).fetchall()
            
            return [
                StoredTrack(
                    media_server_rating_key=row["media_server_rating_key"],
                    media_server_type=row["media_server_type"],
                    artist=row["artist"],
                    album=row["album"],
                    title=row["title"],
                    filepath=row["filepath"],
                    added_at=datetime.fromisoformat(row["added_at"]),
                    last_scanned=datetime.fromisoformat(row["last_scanned"])
                )
                for row in rows
            ]
    
    def search_tracks(self, search_query: str, limit: Optional[int] = None, offset: int = 0) -> List[StoredTrack]:
        """Search tracks by artist, album, or title."""
        logger.debug(f"Searching tracks with query: '{search_query}', limit: {limit}, offset: {offset}")
        query = """
            SELECT media_server_rating_key, media_server_type, artist, album, title, filepath, added_at, last_scanned
            FROM tracks 
            WHERE artist LIKE ? OR album LIKE ? OR title LIKE ?
            ORDER BY artist, album, title
        """
        
        search_pattern = f"%{search_query}%"
        params = [search_pattern, search_pattern, search_pattern]
        
        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            
            tracks = [
                StoredTrack(
                    media_server_rating_key=row["media_server_rating_key"],
                    media_server_type=row["media_server_type"],
                    artist=row["artist"],
                    album=row["album"],
                    title=row["title"],
                    filepath=row["filepath"],
                    added_at=datetime.fromisoformat(row["added_at"]),
                    last_scanned=datetime.fromisoformat(row["last_scanned"])
                )
                for row in rows
            ]
            
        logger.debug(f"Search found {len(tracks)} tracks matching '{search_query}'")
        return tracks
    
    def count_search_tracks(self, search_query: str) -> int:
        """Count tracks matching search query."""
        query = """
            SELECT COUNT(*) as count
            FROM tracks 
            WHERE artist LIKE ? OR album LIKE ? OR title LIKE ?
        """
        
        search_pattern = f"%{search_query}%"
        params = [search_pattern, search_pattern, search_pattern]
        
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(query, params).fetchone()
            return result[0]
    
    def search_tracks_advanced(
        self, 
        artist: Optional[str] = None,
        album: Optional[str] = None, 
        title: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[StoredTrack]:
        """Search tracks by specific artist, album, and/or title criteria using AND logic."""
        logger.debug(f"Advanced search: artist='{artist}', album='{album}', title='{title}', limit={limit}, offset={offset}")
        conditions = []
        params = []
        
        if artist and artist.strip():
            conditions.append("artist LIKE ?")
            params.append(f"%{artist.strip()}%")
            
        if album and album.strip():
            conditions.append("album LIKE ?")
            params.append(f"%{album.strip()}%")
            
        if title and title.strip():
            conditions.append("title LIKE ?")
            params.append(f"%{title.strip()}%")
        
        if not conditions:
            # If no search criteria provided, return all tracks
            logger.debug("No search criteria provided, returning all tracks")
            return self.get_all_tracks(limit=limit, offset=offset)
        
        query = f"""
            SELECT media_server_rating_key, media_server_type, artist, album, title, filepath, added_at, last_scanned
            FROM tracks 
            WHERE {' AND '.join(conditions)}
            ORDER BY artist, album, title
        """
        
        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            
            tracks = [
                StoredTrack(
                    media_server_rating_key=row["media_server_rating_key"],
                    media_server_type=row["media_server_type"],
                    artist=row["artist"],
                    album=row["album"],
                    title=row["title"],
                    filepath=row["filepath"],
                    added_at=datetime.fromisoformat(row["added_at"]),
                    last_scanned=datetime.fromisoformat(row["last_scanned"])
                )
                for row in rows
            ]
            
        logger.debug(f"Advanced search found {len(tracks)} tracks")
        return tracks
    
    def count_search_tracks_advanced(
        self,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        title: Optional[str] = None
    ) -> int:
        """Count tracks matching advanced search criteria."""
        conditions = []
        params = []
        
        if artist and artist.strip():
            conditions.append("artist LIKE ?")
            params.append(f"%{artist.strip()}%")
            
        if album and album.strip():
            conditions.append("album LIKE ?")
            params.append(f"%{album.strip()}%")
            
        if title and title.strip():
            conditions.append("title LIKE ?")
            params.append(f"%{title.strip()}%")
        
        if not conditions:
            # If no search criteria provided, return total count
            return self.get_track_count()
        
        query = f"""
            SELECT COUNT(*) as count
            FROM tracks 
            WHERE {' AND '.join(conditions)}
        """
        
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(query, params).fetchone()
            return result[0]
    
    def get_track_count(self) -> int:
        """Get total number of tracks in the database."""
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute("SELECT COUNT(*) as count FROM tracks").fetchone()
            return result[0]
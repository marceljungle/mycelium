"""SQLite database for storing track metadata and processing state."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..domain.models import Track
from ..config_yaml import get_user_data_dir


@dataclass
class StoredTrack:
    """Track with additional metadata for database storage."""
    plex_rating_key: str
    artist: str
    album: str
    title: str
    filepath: str
    added_at: datetime
    last_scanned: datetime
    embedding_processed: bool = False
    embedding_processed_at: Optional[datetime] = None
    
    def to_track(self) -> Track:
        """Convert to domain Track model."""
        return Track(
            artist=self.artist,
            album=self.album,
            title=self.title,
            filepath=Path(self.filepath),
            plex_rating_key=self.plex_rating_key
        )
    
    @classmethod
    def from_track(cls, track: Track, added_at: datetime = None) -> "StoredTrack":
        """Create StoredTrack from domain Track model."""
        now = datetime.utcnow()
        return cls(
            plex_rating_key=track.plex_rating_key,
            artist=track.artist,
            album=track.album,
            title=track.title,
            filepath=str(track.filepath),
            added_at=added_at or now,
            last_scanned=now,
            embedding_processed=False
        )


class TrackDatabase:
    """SQLite database for managing track metadata and processing state."""
    
    def __init__(self, db_path: Optional[str]):
        # Default to user data directory if path is not provided
        if not db_path:
            db_path = str(get_user_data_dir() / "mycelium_tracks.db")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tracks (
                    plex_rating_key TEXT PRIMARY KEY,
                    artist TEXT NOT NULL,
                    album TEXT NOT NULL,
                    title TEXT NOT NULL,
                    filepath TEXT NOT NULL,
                    added_at TIMESTAMP NOT NULL,
                    last_scanned TIMESTAMP NOT NULL,
                    embedding_processed BOOLEAN DEFAULT FALSE,
                    embedding_processed_at TIMESTAMP NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scan_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP NULL,
                    tracks_found INTEGER DEFAULT 0,
                    tracks_new INTEGER DEFAULT 0,
                    tracks_updated INTEGER DEFAULT 0
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processing_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP NULL,
                    total_tracks INTEGER DEFAULT 0,
                    processed_tracks INTEGER DEFAULT 0,
                    failed_tracks INTEGER DEFAULT 0,
                    is_resumable BOOLEAN DEFAULT TRUE
                )
            """)
            
            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_processed ON tracks(embedding_processed)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_scanned ON tracks(last_scanned)")
            conn.commit()
    
    def start_scan_session(self) -> int:
        """Start a new scan session and return session ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO scan_sessions (started_at) VALUES (?)",
                (datetime.utcnow(),)
            )
            return cursor.lastrowid
    
    def complete_scan_session(self, session_id: int, tracks_found: int, tracks_new: int, tracks_updated: int) -> None:
        """Complete a scan session with statistics."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE scan_sessions 
                SET completed_at = ?, tracks_found = ?, tracks_new = ?, tracks_updated = ?
                WHERE id = ?
            """, (datetime.utcnow(), tracks_found, tracks_new, tracks_updated, session_id))
            conn.commit()
    
    def save_tracks(self, tracks: List[Track], scan_timestamp: datetime = None) -> Dict[str, int]:
        """Save tracks to database, return statistics."""
        if scan_timestamp is None:
            scan_timestamp = datetime.utcnow()
        
        stats = {"new": 0, "updated": 0, "total": len(tracks)}
        
        with sqlite3.connect(self.db_path) as conn:
            for track in tracks:
                # Check if track exists
                existing = conn.execute(
                    "SELECT plex_rating_key, last_scanned FROM tracks WHERE plex_rating_key = ?",
                    (track.plex_rating_key,)
                ).fetchone()
                
                if existing:
                    # Update existing track
                    conn.execute("""
                        UPDATE tracks 
                        SET artist = ?, album = ?, title = ?, filepath = ?, last_scanned = ?
                        WHERE plex_rating_key = ?
                    """, (track.artist, track.album, track.title, str(track.filepath), 
                         scan_timestamp, track.plex_rating_key))
                    stats["updated"] += 1
                else:
                    # Insert new track
                    conn.execute("""
                        INSERT INTO tracks 
                        (plex_rating_key, artist, album, title, filepath, added_at, last_scanned)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (track.plex_rating_key, track.artist, track.album, track.title,
                         str(track.filepath), scan_timestamp, scan_timestamp))
                    stats["new"] += 1
            
            conn.commit()
        
        return stats
    
    def get_unprocessed_tracks(self, limit: Optional[int] = None) -> List[StoredTrack]:
        """Get tracks that haven't been processed for embeddings."""
        query = """
            SELECT plex_rating_key, artist, album, title, filepath, added_at, last_scanned,
                   embedding_processed, embedding_processed_at
            FROM tracks 
            WHERE embedding_processed = FALSE
            ORDER BY added_at
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query).fetchall()
            
            return [
                StoredTrack(
                    plex_rating_key=row["plex_rating_key"],
                    artist=row["artist"],
                    album=row["album"],
                    title=row["title"],
                    filepath=row["filepath"],
                    added_at=datetime.fromisoformat(row["added_at"]),
                    last_scanned=datetime.fromisoformat(row["last_scanned"]),
                    embedding_processed=bool(row["embedding_processed"]),
                    embedding_processed_at=datetime.fromisoformat(row["embedding_processed_at"]) if row["embedding_processed_at"] else None
                )
                for row in rows
            ]
    
    def mark_track_processed(self, plex_rating_key: str, processed_at: datetime = None) -> None:
        """Mark a track as processed for embeddings."""
        if processed_at is None:
            processed_at = datetime.utcnow()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE tracks 
                SET embedding_processed = TRUE, embedding_processed_at = ?
                WHERE plex_rating_key = ?
            """, (processed_at, plex_rating_key))
            conn.commit()
    
    def get_processing_stats(self) -> Dict[str, int]:
        """Get processing statistics."""
        with sqlite3.connect(self.db_path) as conn:
            stats = {}
            
            result = conn.execute("SELECT COUNT(*) as total FROM tracks").fetchone()
            stats["total_tracks"] = result[0]
            
            result = conn.execute("SELECT COUNT(*) as processed FROM tracks WHERE embedding_processed = TRUE").fetchone()
            stats["processed_tracks"] = result[0]
            
            stats["unprocessed_tracks"] = stats["total_tracks"] - stats["processed_tracks"]
            
            return stats
    
    def start_processing_session(self, total_tracks: int) -> int:
        """Start a new processing session and return session ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO processing_sessions (started_at, total_tracks)
                VALUES (?, ?)
            """, (datetime.utcnow(), total_tracks))
            return cursor.lastrowid
    
    def update_processing_session(self, session_id: int, processed_count: int, failed_count: int = 0) -> None:
        """Update processing session progress."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE processing_sessions 
                SET processed_tracks = ?, failed_tracks = ?
                WHERE id = ?
            """, (processed_count, failed_count, session_id))
            conn.commit()
    
    def complete_processing_session(self, session_id: int) -> None:
        """Complete a processing session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE processing_sessions 
                SET completed_at = ?, is_resumable = FALSE
                WHERE id = ?
            """, (datetime.utcnow(), session_id))
            conn.commit()
    
    def get_latest_processing_session(self) -> Optional[Dict[str, Any]]:
        """Get the latest processing session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("""
                SELECT * FROM processing_sessions 
                ORDER BY started_at DESC 
                LIMIT 1
            """).fetchone()
            
            if row:
                return dict(row)
            return None


    def get_track_by_id(self, plex_rating_key: str) -> Optional[StoredTrack]:
        """Get a specific track by Plex rating key."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("""
                SELECT plex_rating_key, artist, album, title, filepath, added_at, last_scanned,
                       embedding_processed, embedding_processed_at
                FROM tracks 
                WHERE plex_rating_key = ?
            """, (plex_rating_key,)).fetchone()
            
            if row:
                return StoredTrack(
                    plex_rating_key=row["plex_rating_key"],
                    artist=row["artist"],
                    album=row["album"],
                    title=row["title"],
                    filepath=row["filepath"],
                    added_at=datetime.fromisoformat(row["added_at"]),
                    last_scanned=datetime.fromisoformat(row["last_scanned"]),
                    embedding_processed=bool(row["embedding_processed"]),
                    embedding_processed_at=datetime.fromisoformat(row["embedding_processed_at"]) if row["embedding_processed_at"] else None
                )
            return None
    
    def get_all_tracks(self, limit: Optional[int] = None, offset: int = 0) -> List[StoredTrack]:
        """Get all tracks from the database with optional pagination."""
        query = """
            SELECT plex_rating_key, artist, album, title, filepath, added_at, last_scanned,
                   embedding_processed, embedding_processed_at
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
                    plex_rating_key=row["plex_rating_key"],
                    artist=row["artist"],
                    album=row["album"],
                    title=row["title"],
                    filepath=row["filepath"],
                    added_at=datetime.fromisoformat(row["added_at"]),
                    last_scanned=datetime.fromisoformat(row["last_scanned"]),
                    embedding_processed=bool(row["embedding_processed"]),
                    embedding_processed_at=datetime.fromisoformat(row["embedding_processed_at"]) if row["embedding_processed_at"] else None
                )
                for row in rows
            ]
    
    def search_tracks(self, search_query: str, limit: Optional[int] = None, offset: int = 0) -> List[StoredTrack]:
        """Search tracks by artist, album, or title."""
        query = """
            SELECT plex_rating_key, artist, album, title, filepath, added_at, last_scanned,
                   embedding_processed, embedding_processed_at
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
            
            return [
                StoredTrack(
                    plex_rating_key=row["plex_rating_key"],
                    artist=row["artist"],
                    album=row["album"],
                    title=row["title"],
                    filepath=row["filepath"],
                    added_at=datetime.fromisoformat(row["added_at"]),
                    last_scanned=datetime.fromisoformat(row["last_scanned"]),
                    embedding_processed=bool(row["embedding_processed"]),
                    embedding_processed_at=datetime.fromisoformat(row["embedding_processed_at"]) if row["embedding_processed_at"] else None
                )
                for row in rows
            ]
    
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
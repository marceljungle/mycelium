"""In-memory structured error log for surfacing processing errors in the UI."""

import logging
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Keep the last N entries in memory (ring buffer).
_MAX_ENTRIES = 500


@dataclass
class ErrorLogEntry:
    """A single structured error event."""

    id: str
    timestamp: datetime
    category: str  # e.g. "download_404", "download_timeout", "processing", …
    message: str
    track_id: Optional[str] = None
    track_artist: Optional[str] = None
    track_title: Optional[str] = None
    track_album: Optional[str] = None
    worker_id: Optional[str] = None
    task_id: Optional[str] = None


class ErrorLog:
    """Thread-safe ring-buffer of structured error entries."""

    def __init__(self, max_entries: int = _MAX_ENTRIES) -> None:
        self._entries: Deque[ErrorLogEntry] = deque(maxlen=max_entries)
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add(
        self,
        category: str,
        message: str,
        *,
        track_id: Optional[str] = None,
        track_artist: Optional[str] = None,
        track_title: Optional[str] = None,
        track_album: Optional[str] = None,
        worker_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> ErrorLogEntry:
        """Append an error entry and return it."""
        entry = ErrorLogEntry(
            id=uuid.uuid4().hex[:12],
            timestamp=datetime.now(),
            category=category,
            message=message,
            track_id=track_id,
            track_artist=track_artist,
            track_title=track_title,
            track_album=track_album,
            worker_id=worker_id,
            task_id=task_id,
        )
        with self._lock:
            self._entries.append(entry)
        return entry

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_entries(
        self,
        *,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[ErrorLogEntry], int]:
        """Return entries newest-first, optionally filtered by category.

        Returns:
            ``(entries, total_count)`` after applying *category* filter
            but **before** limit/offset.
        """
        with self._lock:
            if category:
                matching = [e for e in self._entries if e.category == category]
            else:
                matching = list(self._entries)

        # Newest-first
        matching.reverse()
        total = len(matching)
        page = matching[offset : offset + limit]
        return page, total

    def get_categories(self) -> Dict[str, int]:
        """Return a ``{category: count}`` dict for all current entries."""
        with self._lock:
            counts: Dict[str, int] = {}
            for e in self._entries:
                counts[e.category] = counts.get(e.category, 0) + 1
        return counts

    def clear(self) -> int:
        """Remove all entries. Returns the number removed."""
        with self._lock:
            n = len(self._entries)
            self._entries.clear()
        return n


# Module-level singleton so it can be imported from anywhere.
error_log = ErrorLog()

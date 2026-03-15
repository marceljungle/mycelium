"""Shared status state between client worker and client API."""

import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ClientWorkerStatus:
    """Thread-safe snapshot of the client worker's runtime state."""

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    is_running: bool = False
    is_processing: bool = False
    jobs_in_download_queue: int = 0
    jobs_ready_for_gpu: int = 0
    total_jobs_processed: int = 0
    current_batch_size: int = 0
    last_job_completed_at: Optional[float] = None
    worker_id: Optional[str] = None
    server_url: Optional[str] = None
    model_type: Optional[str] = None
    model_id: Optional[str] = None

    def update(self, **kwargs: object) -> None:
        """Atomically update one or more status fields."""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key) and not key.startswith("_"):
                    setattr(self, key, value)

    def to_dict(self) -> dict:
        """Return a plain-dict snapshot (safe to serialise to JSON)."""
        with self._lock:
            return {
                "is_running": self.is_running,
                "is_processing": self.is_processing,
                "jobs_in_download_queue": self.jobs_in_download_queue,
                "jobs_ready_for_gpu": self.jobs_ready_for_gpu,
                "total_jobs_processed": self.total_jobs_processed,
                "current_batch_size": self.current_batch_size,
                "last_job_completed_at": self.last_job_completed_at,
                "worker_id": self.worker_id,
                "server_url": self.server_url,
                "model_type": self.model_type,
                "model_id": self.model_id,
            }


# Module-level singleton — imported by both client.py and client_app.py
worker_status = ClientWorkerStatus()

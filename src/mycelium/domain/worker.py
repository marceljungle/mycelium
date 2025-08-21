"""Worker domain models for client-server coordination."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional


class TaskType(str, Enum):
    """Type of tasks that can be assigned to workers."""
    COMPUTE_EMBEDDING = "compute_embedding"
    COMPUTE_TEXT_EMBEDDING = "compute_text_embedding"
    COMPUTE_AUDIO_EMBEDDING = "compute_audio_embedding"


class TaskStatus(str, Enum):
    """Status of a task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class Worker:
    """Represents a worker in the system."""
    id: str
    ip_address: str
    registration_time: datetime
    last_heartbeat: datetime
    is_active: bool = True


@dataclass
class Task:
    """Represents a task to be processed by a worker."""
    task_id: str
    task_type: TaskType
    track_id: str
    download_url: str
    status: TaskStatus = TaskStatus.PENDING
    assigned_worker_id: Optional[str] = None
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    # Additional fields for search tasks
    text_query: Optional[str] = None  # For text search tasks
    audio_data: Optional[bytes] = None  # For audio search tasks
    audio_filename: Optional[str] = None  # For audio search tasks
    n_results: Optional[int] = None  # For search tasks - number of results to return
    # Results storage for search tasks
    search_results: Optional[List[dict]] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class TaskResult:
    """Result of a completed task."""
    task_id: str
    track_id: str
    status: TaskStatus
    embedding: Optional[List[float]] = None
    error_message: Optional[str] = None
    # For search tasks, we store the search results directly
    search_results: Optional[List[dict]] = None
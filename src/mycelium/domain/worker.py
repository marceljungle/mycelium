"""Worker domain models for client-server coordination."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID


class TaskType(str, Enum):
    """Type of tasks that can be assigned to workers."""
    COMPUTE_EMBEDDING = "compute_embedding"


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
"""API models for worker coordination."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from ..domain.worker import TaskType, TaskStatus


class WorkerRegistrationRequest(BaseModel):
    """Request model for worker registration."""
    worker_id: str
    ip_address: str


class WorkerRegistrationResponse(BaseModel):
    """Response model for worker registration."""
    worker_id: str
    registration_time: str
    message: str
    embedding_config: Dict[str, Any]


class JobRequest(BaseModel):
    """Response model for job requests."""
    task_id: str
    task_type: TaskType
    track_id: str
    download_url: str
    text_query: Optional[str] = None
    audio_filename: Optional[str] = None
    n_results: Optional[int] = None


class TaskResultRequest(BaseModel):
    """Request model for task result submission."""
    task_id: str
    track_id: str
    status: TaskStatus
    embedding: Optional[List[float]] = None
    error_message: Optional[str] = None
    search_results: Optional[List[dict]] = None


class TaskResultResponse(BaseModel):
    """Response model for task result submission."""
    success: bool
    message: str
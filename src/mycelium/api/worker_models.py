"""API models for worker coordination."""

from typing import List, Optional

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


class JobRequest(BaseModel):
    """Response model for job requests."""
    task_id: str
    task_type: TaskType
    track_id: str
    download_url: str


class TaskResultRequest(BaseModel):
    """Request model for task result submission."""
    task_id: str
    track_id: str
    status: TaskStatus
    embedding: Optional[List[float]] = None
    error_message: Optional[str] = None


class TaskResultResponse(BaseModel):
    """Response model for task result submission."""
    success: bool
    message: str


class ConfirmationRequiredResponse(BaseModel):
    """Response when user confirmation is required."""
    status: str
    message: str
    track_id: str


class ComputeOnServerRequest(BaseModel):
    """Request model for server-side computation."""
    track_id: str


class QueueStatsResponse(BaseModel):
    """Response model for queue statistics."""
    active_workers: int
    pending_tasks: int
    in_progress_tasks: int
    completed_tasks: int
    failed_tasks: int
    total_tasks: int


class WorkerProcessingResponse(BaseModel):
    """Response when worker processing is initiated."""
    status: str
    message: str
    track_id: str
    task_id: Optional[str] = None


class NoWorkersResponse(BaseModel):
    """Response when no workers are available."""
    status: str
    message: str
    active_workers: int
    confirmation_required: bool
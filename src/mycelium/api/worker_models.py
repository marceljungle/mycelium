"""API models for worker coordination."""

from typing import List, Optional

from pydantic import BaseModel, Field

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
    text_query: Optional[str] = None  # For text search tasks
    audio_filename: Optional[str] = None  # For audio search tasks
    n_results: Optional[int] = None  # For search tasks


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


class ConfirmationRequiredResponse(BaseModel):
    """Response when user confirmation is required."""
    status: str
    message: str
    track_id: str


class ComputeOnServerRequest(BaseModel):
    """Request model for server-side computation."""
    track_id: str


class WorkerProcessingResponse(BaseModel):
    """Response when worker processing is initiated."""
    status: str
    message: str
    track_id: Optional[str] = None
    task_id: Optional[str] = None
    tasks_created: Optional[int] = None
    active_workers: Optional[int] = None


class NoWorkersResponse(BaseModel):
    """Response when no workers are available."""
    status: str
    message: str
    active_workers: int
    confirmation_required: bool


class SearchProcessingResponse(BaseModel):
    """Response when search task is processing on workers."""
    status: str
    message: str
    task_id: str
    query: Optional[str] = None  # For text search
    filename: Optional[str] = None  # For audio search


class SearchConfirmationRequiredResponse(BaseModel):
    """Response when search requires user confirmation for server processing."""
    status: str
    query: Optional[str] = None  # For text search  
    filename: Optional[str] = None  # For audio search


class ComputeSearchOnServerRequest(BaseModel):
    """Request model for server-side search computation."""
    query: Optional[str] = None  # For text search
    n_results: int = 10
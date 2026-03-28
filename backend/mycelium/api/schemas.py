"""DTOs for the Mycelium API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Track / Search
# ---------------------------------------------------------------------------

class TrackResponse(BaseModel):
    """A single track from the library."""

    artist: str
    album: str
    title: str
    filepath: str
    media_server_rating_key: str
    media_server_type: str
    processed: Optional[bool] = None
    thumb_url: Optional[str] = None


class SearchResultResponse(BaseModel):
    """A search result with similarity metadata."""

    track: TrackResponse
    similarity_score: float
    distance: float


class TracksListResponse(BaseModel):
    """Paginated list of library tracks."""

    tracks: List[TrackResponse]
    total_count: int
    page: int
    limit: int


# ---------------------------------------------------------------------------
# Library operations
# ---------------------------------------------------------------------------

class LibraryStatsResponse(BaseModel):
    """Statistics about the music library."""

    total_embeddings: int
    collection_name: str
    database_path: str
    track_database_stats: Optional[TrackDatabaseStats] = None


class TrackDatabaseStats(BaseModel):
    """Processing progress statistics."""

    total_tracks: int
    processed_tracks: int
    unprocessed_tracks: int
    progress_percentage: float
    is_processing: Optional[bool] = None
    model_id: Optional[str] = None


# Rebuild LibraryStatsResponse now that TrackDatabaseStats is defined
LibraryStatsResponse.model_rebuild()


class ScanLibraryResponse(BaseModel):
    """Result of a library scan operation."""

    message: str
    total_tracks: int
    new_tracks: int
    updated_tracks: int
    scan_timestamp: str


class ProcessingResponse(BaseModel):
    """Multi-purpose response for async processing endpoints."""

    status: str
    message: Optional[str] = None
    task_id: Optional[str] = None
    track_id: Optional[str] = None
    query: Optional[str] = None
    filename: Optional[str] = None
    active_workers: Optional[int] = None
    tasks_created: Optional[int] = None
    confirmation_required: Optional[bool] = None


class StopProcessingResponse(BaseModel):
    """Response when stopping embedding processing."""

    message: str
    type: Optional[str] = None
    cleared_tasks: Optional[int] = None


# ---------------------------------------------------------------------------
# Playlists
# ---------------------------------------------------------------------------

class CreatePlaylistRequest(BaseModel):
    """Request body to create a playlist."""

    name: str
    track_ids: List[str]
    batch_size: int = 100


class PlaylistResponse(BaseModel):
    """Confirmation that a playlist was created."""

    name: str
    track_count: int
    created_at: str
    server_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Task queue
# ---------------------------------------------------------------------------

class TaskStatusResponse(BaseModel):
    """Status of an async worker task."""

    task_id: str
    status: str
    track_id: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    search_results: Optional[List[SearchResultResponse]] = None


# ---------------------------------------------------------------------------
# Processing queue dashboard
# ---------------------------------------------------------------------------

class QueueTaskResponse(BaseModel):
    """Detailed view of a single task in the processing queue."""

    task_id: str
    task_type: str
    context_type: str
    status: str
    track_id: Optional[str] = None
    track_artist: Optional[str] = None
    track_title: Optional[str] = None
    track_album: Optional[str] = None
    assigned_worker_id: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    text_query: Optional[str] = None


class QueueWorkerResponse(BaseModel):
    """Worker information for the queue dashboard."""

    id: str
    ip_address: str
    registration_time: str
    last_heartbeat: str
    is_active: bool
    gpu_name: Optional[str] = None
    current_task: Optional[QueueTaskResponse] = None


class QueueStatsResponse(BaseModel):
    """Aggregate counts for the queue dashboard."""

    active_workers: int = 0
    pending_tasks: int = 0
    in_progress_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_tasks: int = 0


class QueueOverviewResponse(BaseModel):
    """Top-level overview: workers + stats + in-progress tasks."""

    workers: List[QueueWorkerResponse]
    stats: QueueStatsResponse
    in_progress_tasks: List[QueueTaskResponse]


class QueueTasksListResponse(BaseModel):
    """Paginated list of tasks for a given status filter."""

    tasks: List[QueueTaskResponse]
    total_count: int
    limit: int
    offset: int


class CancelTaskResponse(BaseModel):
    """Response after attempting to cancel a task."""

    success: bool
    message: str


# ---------------------------------------------------------------------------
# Server config (GET / POST /api/config)
# ---------------------------------------------------------------------------

class ConfigResponse(BaseModel):
    """Full server configuration (returned by GET /api/config)."""

    media_server: Dict[str, Any]
    plex: Dict[str, Any]
    server: Dict[str, Any]
    api: Dict[str, Any]
    chroma: Dict[str, Any]
    embedding: Dict[str, Any]
    clap: Dict[str, Any]
    muq: Dict[str, Any]
    logging: Dict[str, Any]


class ConfigRequest(BaseModel):
    """Body sent when saving server configuration."""

    media_server: Dict[str, Any]
    plex: Dict[str, Any]
    api: Dict[str, Any]
    chroma: Dict[str, Any]
    embedding: Optional[Dict[str, Any]] = None
    clap: Dict[str, Any]
    muq: Optional[Dict[str, Any]] = None
    server: Dict[str, Any]
    logging: Dict[str, Any]
    database: Optional[Dict[str, Any]] = None


class SaveConfigResponse(BaseModel):
    """Confirmation after saving configuration."""

    message: str
    status: str
    reloaded: bool
    reload_error: Optional[str] = None


# ---------------------------------------------------------------------------
# Worker (client) config — used by client_app.py
# ---------------------------------------------------------------------------

class WorkerConfigResponse(BaseModel):
    """Full worker configuration (returned by GET /api/config on worker)."""

    client: Dict[str, Any]
    client_api: Dict[str, Any]
    logging: Dict[str, Any]


class WorkerConfigRequest(BaseModel):
    """Body sent when saving worker configuration."""

    client: Dict[str, Any]
    client_api: Dict[str, Any]
    logging: Dict[str, Any]


# ---------------------------------------------------------------------------
# Client worker status — used by client_app.py GET /api/status
# ---------------------------------------------------------------------------

class WorkerProcessingStatus(BaseModel):
    """Live snapshot of the client worker thread."""

    is_running: bool = False
    is_processing: bool = False
    is_stopping: bool = False
    jobs_in_download_queue: int = 0
    jobs_ready_for_gpu: int = 0
    total_jobs_processed: int = 0
    current_batch_size: int = 0
    last_job_completed_at: Optional[float] = None
    worker_id: Optional[str] = None
    server_url: Optional[str] = None
    model_type: Optional[str] = None
    model_id: Optional[str] = None
    micro_batch_size: Optional[int] = None


class ClientStatusResponse(BaseModel):
    """Aggregated client status (server reachability + worker state)."""

    server_reachable: bool
    worker: WorkerProcessingStatus


class StopClientResponse(BaseModel):
    """Response after requesting a graceful worker stop."""

    success: bool
    message: str


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------

class CapabilitiesResponse(BaseModel):
    """Describes what the current model configuration supports."""

    embedding_model_type: str
    model_id: str
    supports_text_search: bool
    supports_audio_search: bool
    supports_similar_tracks: bool


# ---------------------------------------------------------------------------
# Compute-on-server helpers
# ---------------------------------------------------------------------------

class ComputeOnServerRequest(BaseModel):
    """Request to compute an embedding on the server (after user confirmation)."""

    track_id: str


class ComputeSearchOnServerRequest(BaseModel):
    """Request to run a search on the server (after user confirmation)."""

    query: Optional[str] = None
    n_results: int = 10


# ---------------------------------------------------------------------------
# Error log viewer
# ---------------------------------------------------------------------------

class ErrorLogEntryResponse(BaseModel):
    """A single structured error event."""

    id: str
    timestamp: str
    category: str
    message: str
    track_id: Optional[str] = None
    track_artist: Optional[str] = None
    track_title: Optional[str] = None
    track_album: Optional[str] = None
    worker_id: Optional[str] = None
    task_id: Optional[str] = None


class ErrorLogResponse(BaseModel):
    """Paginated list of error log entries."""

    entries: List[ErrorLogEntryResponse]
    total_count: int
    categories: Dict[str, int]

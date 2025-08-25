"""FastAPI application for Mycelium web interface."""

import functools
import logging
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .worker_models import (
    WorkerRegistrationRequest, WorkerRegistrationResponse,
    JobRequest, TaskResultRequest, TaskResultResponse,
    ConfirmationRequiredResponse, ComputeOnServerRequest,
    WorkerProcessingResponse, NoWorkersResponse,
    SearchProcessingResponse, SearchConfirmationRequiredResponse,
    ComputeSearchOnServerRequest
)
from ..application.job_queue import JobQueueService
from ..application.services import MyceliumService
from ..config import MyceliumConfig, PlexConfig, CLAPConfig, ChromaConfig, DatabaseConfig, APIConfig, LoggingConfig
from ..domain.worker import TaskResult, TaskType, TaskStatus, ContextType

# Setup logger for this module
logger = logging.getLogger(__name__)


# Pydantic models for API
class TrackResponse(BaseModel):
    artist: str
    album: str
    title: str
    filepath: str
    media_server_rating_key: str
    media_server_type: str
    
    @classmethod
    def from_domain(cls, track) -> "TrackResponse":
        """Create from domain Track object."""
        return cls(
            artist=track.artist,
            album=track.album,
            title=track.title,
            filepath=str(track.filepath),
            media_server_rating_key=track.media_server_rating_key,
            media_server_type=track.media_server_type.value
        )


class SearchResultResponse(BaseModel):
    track: TrackResponse
    similarity_score: float
    distance: float


class CreatePlaylistRequest(BaseModel):
    name: str
    track_ids: List[str]


class PlaylistResponse(BaseModel):
    name: str
    track_count: int
    created_at: str
    server_id: Optional[str] = None


class TrackDatabaseStats(BaseModel):
    total_tracks: int
    processed_tracks: int
    unprocessed_tracks: int
    progress_percentage: float
    is_processing: Optional[bool] = None
    latest_session: Optional[Dict[str, Any]] = None


class LibraryStatsResponse(BaseModel):
    total_embeddings: int
    collection_name: str
    database_path: str
    track_database_stats: Optional[TrackDatabaseStats] = None


class SearchRequest(BaseModel):
    query: str
    n_results: int = 10


class ConfigRequest(BaseModel):
    """Request model for updating configuration."""
    plex: Dict[str, Any]
    api: Dict[str, Any]
    chroma: Dict[str, Any]
    clap: Dict[str, Any]
    logging: Dict[str, Any]
    database: Optional[Dict[str, Any]] = None


class TracksListResponse(BaseModel):
    """Response model for tracks listing."""
    tracks: List[TrackResponse]
    total_count: int
    page: int
    limit: int


# Initialize configuration and service
config = MyceliumConfig.load_from_yaml()

# Setup logging
config.setup_logging()

logger.info("Initializing Mycelium service...")

# Initialize the main service
service = MyceliumService(
    plex_url=config.plex.url,
    plex_token=config.plex.token,
    music_library_name=config.plex.music_library_name,
    db_path=config.chroma.get_db_path(),
    collection_name=config.chroma.collection_name,
    model_id=config.clap.model_id,
    track_db_path=config.database.get_db_path()
)

# Initialize job queue service
job_queue = JobQueueService()

# Initialize worker processing in the service
service.initialize_worker_processing(job_queue, config.api.host, config.api.port)

# Global lock for thread-safe config reloading
config_lock = threading.RLock()

def with_service_lock(func):
    """Decorator to ensure thread-safe access to service and config."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        with config_lock:
            return await func(*args, **kwargs)
    return wrapper

def reload_config() -> None:
    """Reload configuration and reinitialize services."""
    global config, service, job_queue
    
    with config_lock:
        try:
            logger.info("Reloading configuration...")
            
            # Load new configuration
            new_config = MyceliumConfig.load_from_yaml()
            
            # Update logging if level changed
            if new_config.logging.level != config.logging.level:
                new_config.setup_logging()
                logger.info(f"Updated logging level to {new_config.logging.level}")
            
            # Reinitialize service with new configuration
            new_service = MyceliumService(
                plex_url=new_config.plex.url,
                plex_token=new_config.plex.token,
                music_library_name=new_config.plex.music_library_name,
                db_path=new_config.chroma.get_db_path(),
                collection_name=new_config.chroma.collection_name,
                model_id=new_config.clap.model_id,
                track_db_path=new_config.database.get_db_path()
            )
            
            # Reinitialize job queue service
            new_job_queue = JobQueueService()
            
            # Initialize worker processing in the new service
            new_service.initialize_worker_processing(new_job_queue, new_config.api.host, new_config.api.port)
            
            # Update global references atomically
            old_config = config
            old_service = service
            old_job_queue = job_queue
            
            config = new_config
            service = new_service
            job_queue = new_job_queue
            
            logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}", exc_info=True)
            raise

# Create FastAPI app
app = FastAPI(
    title="Mycelium API",
    description="Plex music collection and recommendation system using CLAP embeddings",
    version="0.1.0"
)

# Add CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=False,  # Must be False when using allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint with basic information."""
    return {
        "message": "Mycelium Music Recommendation API",
        "version": "0.1.0",
        "endpoints": {
            "library_stats": "/api/library/stats",
            "library_tracks": "/api/library/tracks",
            "search_text": "/api/search/text",
            "search_audio": "/api/search/audio",
            "compute_text_search": "/compute/search/text",
            "compute_audio_search": "/compute/search/audio",
            "config_get": "/api/config",
            "config_save": "/api/config",
            "scan_library": "/api/library/scan",
            "process_library": "/api/library/process",
            "process_on_server": "/api/library/process/server",
            "stop_processing": "/api/library/process/stop",
            "processing_progress": "/api/library/progress",
            "create_playlist": "/api/playlists/create",
            "worker_register": "/workers/register",
            "worker_get_job": "/workers/get_job",
            "worker_submit_result": "/workers/submit_result",
            "similar_by_track": "/similar/by_track/{track_id}",
            "compute_on_server": "/compute/on_server",
            "download_track": "/download_track/{track_id}",
            "download_audio": "/download_audio/{task_id}",
            "task_status": "/api/queue/task/{task_id}"
        }
    }


@app.get("/api/library/stats", response_model=LibraryStatsResponse)
@with_service_lock
async def get_library_stats():
    """Get statistics about the current music library database."""
    logger.debug("Getting library stats")
    try:
        stats = service.get_database_stats()
        return LibraryStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search/text")
async def search_by_text_get(
        q: str = Query(..., description="Search query"),
        n_results: int = Query(10, description="Number of results to return")
):
    """Search for music tracks by text description (GET endpoint)."""
    logger.info(f"Text search GET request - q: '{q}', n_results: {n_results}")

    try:
        # Check if there are active workers
        active_workers = job_queue.get_active_workers()
        if active_workers:
            logger.info(f"Found {len(active_workers)} active workers, creating text search task")
            # Create task for worker processing
            task = job_queue.create_text_search_task(text_query=q, n_results=n_results, prioritize=True)

            logger.info(f"Created text search task {task.task_id} for query '{q}'")
            # Return processing response
            return SearchProcessingResponse(
                status="processing",
                message="Text embedding computation has been sent to a worker. Please try again in a few moments.",
                task_id=task.task_id,
                query=q
            )

        logger.info(f"No active workers available for text search")
        # No active workers - return confirmation required
        return SearchConfirmationRequiredResponse(
            status="confirmation_required",
            query=q
        )

    except HTTPException:
        # Re-raise HTTP exceptions unchanged
        raise
    except Exception as e:
        logger.error(f"Text search GET failed for q '{q}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search/audio")
async def search_by_audio(
        audio: UploadFile = File(..., description="Audio file to search with"),
        n_results: int = Form(10, description="Number of results to return")
):
    """Search for music tracks by audio file."""
    logger.info(f"Audio search request received - filename: {audio.filename}, content_type: {audio.content_type}")

    try:
        # Validate file type
        if not audio.content_type or not any(
                audio.content_type.startswith(mime)
                for mime in ["audio/", "application/octet-stream"]
        ):
            logger.warning(f"Invalid file type: {audio.content_type}")
            raise HTTPException(status_code=400, detail="Invalid file type. Please upload an audio file.")

        # Read audio content
        content = await audio.read()
        logger.info(f"Audio file read successfully - size: {len(content)} bytes")

        # Check if there are active workers
        active_workers = job_queue.get_active_workers()
        if active_workers:
            logger.info(f"Found {len(active_workers)} active workers, creating audio search task")
            # Create task for worker processing
            task = job_queue.create_task(
                audio_data=content,
                audio_filename=audio.filename or "upload.tmp",
                n_results=n_results,
                prioritize=True,
                context_type=ContextType.AUDIO_SEARCH
            )

            logger.info(f"Created audio search task {task.task_id} for file '{audio.filename}'")
            # Return processing response
            return SearchProcessingResponse(
                status="processing",
                message="Audio embedding computation has been sent to a worker. Please try again in a few moments.",
                task_id=task.task_id,
                filename=audio.filename
            )

        logger.info(f"No active workers available for audio search")
        # No active workers - return confirmation required
        return SearchConfirmationRequiredResponse(
            status="confirmation_required",
            filename=audio.filename
        )

    except HTTPException:
        # Re-raise HTTP exceptions unchanged
        raise
    except Exception as e:
        logger.error(f"Audio search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Audio search failed: {str(e)}")


@app.get("/api/library/tracks", response_model=TracksListResponse)
async def get_library_tracks(
        page: int = Query(1, ge=1, description="Page number (starting from 1)"),
        limit: int = Query(50, ge=1, le=200, description="Number of tracks per page"),
        search: Optional[str] = Query(None, description="Search query for filtering tracks (simple search)"),
        artist: Optional[str] = Query(None, description="Filter by artist name"),
        album: Optional[str] = Query(None, description="Filter by album name"),
        title: Optional[str] = Query(None, description="Filter by track title")
):
    """Get tracks from the library with pagination and optional search.
    
    Supports both simple search (search parameter) and advanced search (artist, album, title parameters).
    Advanced search uses AND logic between fields, while simple search uses OR logic across all fields.
    """
    logger.info(
        f"Library tracks request - page: {page}, limit: {limit}, search: {search}, artist: {artist}, album: {album}, title: {title}")

    try:
        # Determine search type and execute appropriate query
        if artist or album or title:
            # Use advanced search with AND logic
            logger.info(f"Performing advanced library search - artist: {artist}, album: {album}, title: {title}")
            tracks = service.search_tracks_advanced(
                artist=artist,
                album=album,
                title=title,
                limit=limit,
                offset=(page - 1) * limit
            )
            total_count = service.count_tracks_advanced(artist=artist, album=album, title=title)
        elif search and search.strip():
            # Simple search query
            logger.info(f"Performing simple library search for: '{search.strip()}'")
            tracks = service.search_tracks_in_database(search.strip(), limit=limit, offset=(page - 1) * limit)
            total_count = service.count_tracks_in_database(search.strip())
        else:
            # Regular pagination with no search
            offset = (page - 1) * limit
            tracks = service.get_all_tracks(limit=limit, offset=offset)

            # Get total count for pagination info
            stats = service.get_database_stats()
            total_count = stats.get("track_database_stats", {}).get("total_tracks", 0)

        logger.info(f"Retrieved {len(tracks)} tracks from database")

        return TracksListResponse(
            tracks=[
                TrackResponse(
                    artist=track.artist,
                    album=track.album,
                    title=track.title,
                    filepath=str(track.filepath),
                    media_server_rating_key=track.media_server_rating_key,
                    media_server_type=track.media_server_type.value
                )
                for track in tracks
            ],
            total_count=total_count,
            page=page,
            limit=limit
        )
    except Exception as e:
        logger.error(f"Error getting library tracks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get library tracks: {str(e)}")


@app.get("/api/config")
async def get_config():
    """Get current configuration."""
    try:
        logger.info("Configuration get request received")
        # Use thread-safe access to config
        with config_lock:
            # Return current configuration as dict
            config_dict = {
                "plex": {
                    "url": config.plex.url,
                    "token": config.plex.token,
                    "music_library_name": config.plex.music_library_name
                },
                "api": {
                    "host": config.api.host,
                    "port": config.api.port,
                    "reload": config.api.reload
                },
                "chroma": {
                    "collection_name": config.chroma.collection_name,
                    "batch_size": config.chroma.batch_size
                },
                "clap": {
                    "model_id": config.clap.model_id,
                    "target_sr": config.clap.target_sr,
                    "chunk_duration_s": config.clap.chunk_duration_s
                },
                "logging": {
                    "level": config.logging.level
                }
            }
        logger.info("Configuration retrieved successfully")
        return config_dict
    except Exception as e:
        logger.error(f"Failed to get configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get configuration: {str(e)}")


@app.post("/api/config")
async def save_config(config_request: ConfigRequest):
    """Save configuration to YAML file and hot-reload the application."""
    try:
        logger.info("Configuration save request received")

        plex_config = PlexConfig(**config_request.plex)
        clap_config = CLAPConfig(**config_request.clap)
        chroma_config = ChromaConfig(**config_request.chroma)
        database_config = DatabaseConfig()
        api_config = APIConfig(**config_request.api)
        logging_config = LoggingConfig(**config_request.logging)

        yaml_config = MyceliumConfig(
            plex=plex_config,
            clap=clap_config,
            chroma=chroma_config,
            database=database_config,
            api=api_config,
            logging=logging_config
        )

        # Save to default YAML location
        yaml_config.save_to_yaml()
        logger.info("Configuration saved successfully to YAML file")

        # Hot-reload the configuration and services
        try:
            reload_config()
            logger.info("Configuration hot-reloaded successfully")
            return {
                "message": "Configuration saved and reloaded successfully! Changes are now active.",
                "status": "success",
                "reloaded": True
            }
        except Exception as reload_error:
            logger.error(f"Configuration saved but hot-reload failed: {reload_error}", exc_info=True)
            return {
                "message": "Configuration saved successfully, but hot-reload failed. Please restart the server to apply changes.",
                "status": "warning",
                "reloaded": False,
                "reload_error": str(reload_error)
            }
            
    except Exception as e:
        logger.error(f"Failed to save configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save configuration: {str(e)}")


@app.post("/api/library/scan")
@with_service_lock
async def scan_library():
    """Scan the Plex music library and save metadata to database."""
    try:
        result = service.scan_library_to_database()
        return {
            "message": f"Successfully scanned library and saved to database",
            "total_tracks": result["total_tracks"],
            "new_tracks": result["new_tracks"],
            "updated_tracks": result["updated_tracks"],
            "scan_timestamp": result["scan_timestamp"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/library/process")
@with_service_lock
async def process_library():
    """Process embeddings - prioritize workers, fallback to server with confirmation."""
    try:
        # Check if processing is already running
        if service.is_processing_active():
            return {
                "status": "already_running",
                "message": "Processing is already in progress"
            }

        # Check for active workers first
        if service.can_use_workers():
            # Use worker-based processing
            result = service.create_worker_tasks()

            if result["success"]:
                return WorkerProcessingResponse(
                    status="worker_processing_started",
                    message=f"Created {result['tasks_created']} tasks for worker processing",
                    tasks_created=result["tasks_created"],
                    active_workers=result["worker_info"]["active_workers"]
                )
            else:
                return NoWorkersResponse(
                    status="worker_error",
                    message=result["message"],
                    active_workers=0,
                    confirmation_required=False
                )
        else:
            # No workers available - require confirmation for server processing
            return NoWorkersResponse(
                status="no_workers",
                message="No client workers are available. The server hardware may not have sufficient resources for CLAP model processing. Do you want to proceed with server processing anyway?",
                active_workers=0,
                confirmation_required=True
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/library/process/server")
@with_service_lock
async def process_library_on_server(background_tasks: BackgroundTasks):
    """Process embeddings on server after user confirmation."""
    try:
        # Check if processing is already running
        if service.is_processing_active():
            return {
                "message": "Processing is already in progress",
                "status": "already_running"
            }

        # Start processing in background on server
        background_tasks.add_task(service.process_embeddings_from_database)

        return {
            "message": "Server-side embedding processing started in background",
            "status": "server_started"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/library/process/stop")
@with_service_lock
async def stop_processing():
    """Stop the current embedding processing."""
    try:
        service.stop_processing()

        # Also check for worker processing
        if service.has_active_worker_processing():
            worker_result = service.stop_worker_processing()
            return {
                "message": f"Processing stop requested. {worker_result['message']}",
                "cleared_tasks": worker_result.get("cleared_tasks", 0),
                "type": "worker_processing"
            }
        else:
            return {
                "message": "Processing stop requested - will finish current track and stop",
                "type": "server_processing"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/library/progress")
@with_service_lock
async def get_processing_progress(model_id: Optional[str] = Query(None, description="Model ID to get progress for")):
    """Get current processing progress and statistics."""
    logger.debug("Processing progress request received")
    try:
        stats = service.get_processing_progress(model_id)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/playlists/create", response_model=PlaylistResponse)
@with_service_lock
async def create_playlist(request: CreatePlaylistRequest):
    """Create a playlist from a list of track IDs."""
    try:
        playlist = service.create_playlist(request.name, request.track_ids)
        return PlaylistResponse(
            name=playlist.name,
            track_count=playlist.track_count,
            created_at=playlist.created_at.isoformat() if playlist.created_at else "",
            server_id=playlist.server_id
        )
    except Exception as e:
        logger.error(f"Error creating playlist '{request.name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Worker Coordination API
@app.post("/workers/register", response_model=WorkerRegistrationResponse)
async def register_worker(request: WorkerRegistrationRequest):
    """Register a worker with the server."""
    logger.info(f"Worker registration request received for worker ID {request.worker_id}")
    try:
        worker = job_queue.register_worker(request.worker_id, request.ip_address)
        return WorkerRegistrationResponse(
            worker_id=worker.id,
            registration_time=worker.registration_time.isoformat(),
            message="Worker registered successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workers/get_job")
async def get_job(worker_id: str = Query(..., description="Worker ID")):
    """Get the next job for a worker."""
    logger.debug(f"Worker job request received for worker ID {worker_id}")
    try:
        task = job_queue.get_next_job(worker_id)
        if task is None:
            # No job available - return 204 No Content
            logger.debug(f"No job available for worker {worker_id}")
            return None

        logger.info(f"Assigning task {task.task_id} to worker {worker_id} for track {task.track_id}")

        # Workers download files via URL
        return JobRequest(
            task_id=task.task_id,
            task_type=task.task_type,
            track_id=task.track_id,
            download_url=task.download_url,
            text_query=task.text_query,
            audio_filename=task.audio_filename,
            n_results=task.n_results
        )
    except Exception as e:
        logger.error(f"Error getting job for worker {worker_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/workers/submit_result", response_model=TaskResultResponse)
async def submit_result(request: TaskResultRequest):
    """Submit the result of a completed task."""
    try:
        logger.info(
            f"Worker result submission for task {request.task_id}, track {request.track_id}, status: {request.status}")

        task_result = TaskResult(
            task_id=request.task_id,
            track_id=request.track_id,
            status=request.status,
            embedding=request.embedding,
            error_message=request.error_message,
            search_results=request.search_results
        )

        success = job_queue.submit_result(task_result)
        logger.info(f"Task result submission: success={success}")

        # Handle different task types
        if success and request.embedding:
            # Get the task to check its type
            task = job_queue.get_task_status(request.task_id)

            if task and task.task_type == TaskType.COMPUTE_AUDIO_EMBEDDING:
                # Traditional track embedding task
                logger.info(
                    f"Saving worker-generated embedding for track {request.track_id}, size: {len(request.embedding)}")
                if (request.track_id is not None) and (request.track_id.strip() != ""):
                    service.save_embedding(request.track_id, request.embedding)
                    logger.info(f"Successfully saved worker-generated embedding for track {request.track_id}")

                if task.context_type == ContextType.AUDIO_SEARCH:
                    # Audio search task - perform search on server
                    context_info = f"track '{request.track_id}'" if task.track_id else f"file '{task.audio_filename}'"
                    logger.info(f"Performing audio search for task {request.task_id} with {context_info}")
                    try:
                        # Use the embedding to search directly
                        search_results = service.embedding_repository.search_by_embedding(request.embedding,
                                                                                          task.n_results or 10)

                        # Convert to dict format and store in task
                        results_dict = [
                            {
                                "track": {
                                    "artist": result.track.artist,
                                    "album": result.track.album,
                                    "title": result.track.title,
                                    "filepath": str(result.track.filepath),
                                    "media_server_rating_key": result.track.media_server_rating_key,
                                    "media_server_type": result.track.media_server_type.value
                                },
                                "similarity_score": result.similarity_score,
                                "distance": result.distance
                            }
                            for result in search_results
                        ]

                        # Update task with search results - ensure task status is set to success
                        with job_queue._lock:
                            task.search_results = results_dict
                            if task.status != TaskStatus.SUCCESS:
                                logger.info(f"Setting task {request.task_id} status to SUCCESS")
                                task.status = TaskStatus.SUCCESS
                                task.completed_at = datetime.now()

                        logger.info(
                            f"Audio search completed for task {request.task_id}, found {len(results_dict)} results")
                    except Exception as e:
                        logger.error(f"Error performing audio search for task {request.task_id}: {e}", exc_info=True)
                        # Set task status to failed
                        with job_queue._lock:
                            task.status = TaskStatus.FAILED
                            task.error_message = str(e)
                            task.completed_at = datetime.now()

                    # Clean up temporary audio file for audio search tasks
                    job_queue.cleanup_task_files(request.task_id)

            elif task and task.task_type == TaskType.COMPUTE_TEXT_EMBEDDING:
                # Text search task - perform search on server
                logger.info(f"Performing text search for task {request.task_id} with query '{task.text_query}'")
                try:
                    # Use the embedding to search directly
                    search_results = service.embedding_repository.search_by_embedding(request.embedding,
                                                                                      task.n_results or 10)

                    # Convert to dict format and store in task
                    results_dict = [
                        {
                            "track": {
                                "artist": result.track.artist,
                                "album": result.track.album,
                                "title": result.track.title,
                                "filepath": str(result.track.filepath),
                                "media_server_rating_key": result.track.media_server_rating_key,
                                "media_server_type": result.track.media_server_type.value
                            },
                            "similarity_score": result.similarity_score,
                            "distance": result.distance
                        }
                        for result in search_results
                    ]

                    # Update task with search results - ensure task status is set to success
                    with job_queue._lock:
                        task.search_results = results_dict
                        if task.status != TaskStatus.SUCCESS:
                            logger.info(f"Setting task {request.task_id} status to SUCCESS")
                            task.status = TaskStatus.SUCCESS
                            task.completed_at = datetime.now()

                    logger.info(f"Text search completed for task {request.task_id}, found {len(results_dict)} results")
                except Exception as e:
                    logger.error(f"Error performing text search for task {request.task_id}: {e}", exc_info=True)
                    # Set task status to failed
                    with job_queue._lock:
                        task.status = TaskStatus.FAILED
                        task.error_message = str(e)
                        task.completed_at = datetime.now()

                # Clean up any temporary files (for consistency)
                job_queue.cleanup_task_files(request.task_id)
        elif request.error_message:
            logger.error(f"Worker task failed for track {request.track_id}: {request.error_message}")
            # Clean up temporary files for failed tasks
            job_queue.cleanup_task_files(request.task_id)
        else:
            logger.warning(f"Task {request.task_id} completed but no embedding provided")

        return TaskResultResponse(
            success=success,
            message="Result submitted successfully" if success else "Task not found"
        )
    except Exception as e:
        logger.error(f"Error submitting worker result for task {request.task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# File Server for Audio Downloads
@app.get("/download_track/{track_id}")
async def download_track(track_id: str):
    """Download an audio file for processing."""
    logger.debug(f"Download request for track {track_id}")
    try:
        # Get track info from service
        track_info = service.get_track_by_id(track_id)
        if not track_info:
            raise HTTPException(status_code=404, detail="Track not found")

        # Verify file exists
        file_path = Path(track_info.filepath)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Audio file not found")

        # Return file response
        return FileResponse(
            path=str(file_path),
            media_type="application/octet-stream",
            filename=file_path.name
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download_audio/{task_id}")
async def download_audio(task_id: str):
    """Download an audio file for a search task."""
    logger.debug(f"Download request for audio task {task_id}")
    try:
        # Get the temporary file path for this task
        temp_file_path = job_queue.get_audio_task_file(task_id)
        if not temp_file_path or not temp_file_path.exists():
            raise HTTPException(status_code=404, detail="Audio task file not found")

        # Return file response
        return FileResponse(
            path=str(temp_file_path),
            media_type="application/octet-stream",
            filename=f"audio_task_{task_id}.tmp"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Main API for Similar Tracks
@app.get("/similar/by_track/{track_id}")
async def get_similar_tracks(track_id: str, n_results: int = Query(10, description="Number of results")):
    """Find tracks similar to a given track."""
    logger.info(f"Similar tracks request for track_id: {track_id}")

    try:
        # Check if embedding already exists
        has_emb = service.has_embedding(track_id)
        logger.info(f"Embedding check for track {track_id}: {has_emb}")

        if has_emb:
            logger.info(f"Embedding exists for track {track_id}, performing similarity search")
            # Perform similarity search
            results = service.search_similar_by_track_id(track_id, n_results)
            return [
                SearchResultResponse(
                    track=TrackResponse(
                        artist=result.track.artist,
                        album=result.track.album,
                        title=result.track.title,
                        filepath=str(result.track.filepath),
                        media_server_rating_key=result.track.media_server_rating_key,
                        media_server_type=result.track.media_server_type.value
                    ),
                    similarity_score=result.similarity_score,
                    distance=result.distance
                )
                for result in results
            ]

        logger.info(f"No embedding found for track {track_id}, checking for workers")

        # Check if there are active workers
        active_workers = job_queue.get_active_workers()
        if active_workers:
            logger.info(f"Found {len(active_workers)} active workers, creating task")
            # Create task for worker processing
            download_url = f"/download_track/{track_id}"
            task = job_queue.create_task(track_id=track_id, download_url=download_url, prioritize=True,
                                         context_type=ContextType.SIMILAR_TRACKS)

            logger.info(f"Created worker task {task.task_id} for track {track_id}")
            # Return processing response instead of blocking
            response = WorkerProcessingResponse(
                status="processing",
                message="Processing has been sent to a worker. Please try again in a few moments.",
                track_id=track_id,
                task_id=task.task_id
            )
            logger.info(f"Returning worker processing response: {response.model_dump()}")
            return response

        logger.info(f"No active workers available for track {track_id}")
        # No active workers - return confirmation required
        return ConfirmationRequiredResponse(
            status="confirmation_required",
            message="The sonic signature for this song needs to be calculated, and no workers are active. Do you wish to continue on the server hardware?",
            track_id=track_id
        )

    except HTTPException as e:
        logger.error(f"Error in similar tracks endpoint for track {track_id}: {e}", exc_info=True)
        # Re-raise HTTP exceptions as they are
        raise
    except Exception as e:
        logger.error(f"Error in similar tracks endpoint for track {track_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Similar tracks search failed: {str(e)}")


@app.post("/compute/on_server")
async def compute_on_server(request: ComputeOnServerRequest, background_tasks: BackgroundTasks):
    """Compute embedding on server CPU after user confirmation."""
    try:
        logger.info(f"Starting server-side computation for track {request.track_id}")

        # For better UX, process synchronously for single tracks (should be fast enough)
        # Load track info
        track_info = service.get_track_by_id(request.track_id)
        if not track_info:
            logger.warning(f"Track not found for ID: {request.track_id}")
            raise HTTPException(status_code=404, detail="Track not found")

        logger.info(f"Computing embedding for track {request.track_id}: {track_info.artist} - {track_info.title}")

        # Compute embedding on CPU
        embedding = service.compute_embedding_cpu(os.fspath(track_info.filepath))

        if embedding is None or len(embedding) == 0:
            logger.error(f"Failed to compute embedding for track {request.track_id}")
            raise HTTPException(status_code=500, detail="Failed to compute embedding")

        logger.info(f"Successfully computed embedding for track {request.track_id}, size: {len(embedding)}")

        # Save to database
        service.save_embedding(request.track_id, embedding)
        logger.info(f"Successfully computed and saved embedding for track: {request.track_id}")

    except HTTPException:
        # Re-raise HTTP exceptions as they are
        raise
    except Exception as e:
        logger.error(f"Error computing embedding on server for track {request.track_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server computation failed: {str(e)}")


@app.post("/compute/search/text", response_model=List[SearchResultResponse])
async def compute_text_search_on_server(request: ComputeSearchOnServerRequest):
    """Compute text search on server CPU after user confirmation."""
    try:
        if not request.query:
            raise HTTPException(status_code=400, detail="Query is required for text search")

        logger.info(f"Starting server-side text search for query: '{request.query}'")

        # Perform text search directly on server
        results = service.search_similar_by_text(request.query, request.n_results)

        logger.info(f"Text search completed successfully - found {len(results)} results")

        return [
            SearchResultResponse(
                track=TrackResponse(
                    artist=result.track.artist,
                    album=result.track.album,
                    title=result.track.title,
                    filepath=str(result.track.filepath),
                    media_server_rating_key=result.track.media_server_rating_key,
                    media_server_type=result.track.media_server_type.value
                ),
                similarity_score=result.similarity_score,
                distance=result.distance
            )
            for result in results
        ]

    except HTTPException:
        # Re-raise HTTP exceptions as they are
        raise
    except Exception as e:
        logger.error(f"Error computing text search on server for query '{request.query}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server text search failed: {str(e)}")


@app.post("/compute/search/audio", response_model=List[SearchResultResponse])
async def compute_audio_search_on_server(
        audio: UploadFile = File(..., description="Audio file to search with"),
        n_results: int = Form(10, description="Number of results to return")
):
    """Compute audio search on server CPU after user confirmation."""
    try:
        # Validate file type
        if not audio.content_type or not any(
                audio.content_type.startswith(mime)
                for mime in ["audio/", "application/octet-stream"]
        ):
            logger.warning(f"Invalid file type: {audio.content_type}")
            raise HTTPException(status_code=400, detail="Invalid file type. Please upload an audio file.")

        # Read audio content
        content = await audio.read()
        if not content:
            raise HTTPException(status_code=400, detail="Audio data is required for audio search")

        logger.info(f"Starting server-side audio search for file: '{audio.filename}', size: {len(content)} bytes")

        # Create temporary file for the audio data
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            # Perform audio search directly on server
            results = service.search_similar_by_audio(Path(temp_file_path), n_results)

            logger.info(f"Audio search completed successfully - found {len(results)} results")

            return [
                SearchResultResponse(
                    track=TrackResponse(
                        artist=result.track.artist,
                        album=result.track.album,
                        title=result.track.title,
                        filepath=str(result.track.filepath),
                        media_server_rating_key=result.track.media_server_rating_key,
                        media_server_type=result.track.media_server_type.value
                    ),
                    similarity_score=result.similarity_score,
                    distance=result.distance
                )
                for result in results
            ]
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file_path)
            except OSError:
                pass

    except HTTPException:
        # Re-raise HTTP exceptions as they are
        raise
    except Exception as e:
        logger.error(f"Audio search on server failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Audio search failed: {str(e)}")


@app.get("/api/queue/task/{task_id}")
async def get_task_status(task_id: str):
    """Get status of a specific task."""
    try:
        task = job_queue.get_task_status(task_id)
        if task:
            response = {
                "task_id": task.task_id,
                "status": task.status.value,
                "track_id": task.track_id,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "error_message": task.error_message
            }

            # Include search results for search tasks
            if task.search_results:
                response["search_results"] = task.search_results
                logger.debug(
                    f"Task {task_id} status: {task.status.value}, has search_results: {len(task.search_results)} results")
            else:
                logger.debug(f"Task {task_id} status: {task.status.value}, no search_results yet")

            return response
        else:
            logger.warning(f"Task {task_id} not found in queue")
            raise HTTPException(status_code=404, detail="Task not found")
    except Exception as e:
        logger.error(f"Error getting task status for {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting task status: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(
        "mycelium.api.app:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.reload
    )

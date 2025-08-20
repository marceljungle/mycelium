"""FastAPI application for Mycelium web interface."""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import tempfile
import os

from .worker_models import (
    WorkerRegistrationRequest, WorkerRegistrationResponse,
    JobRequest, TaskResultRequest, TaskResultResponse,
    ConfirmationRequiredResponse, ComputeOnServerRequest,
    WorkerProcessingResponse, NoWorkersResponse
)
from ..application.job_queue import JobQueueService
from ..application.services import MyceliumService
from ..config import MyceliumConfig, setup_logging
from ..domain.worker import TaskResult

# Setup logger for this module
logger = logging.getLogger(__name__)


# Pydantic models for API
class TrackResponse(BaseModel):
    artist: str
    album: str
    title: str
    filepath: str
    plex_rating_key: str


class SearchResultResponse(BaseModel):
    track: TrackResponse
    similarity_score: float
    distance: float


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
    client: Dict[str, Any]
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
setup_logging(config.logging.level)

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
            "config_get": "/api/config",
            "config_save": "/api/config",
            "scan_library": "/api/library/scan",
            "process_library": "/api/library/process", 
            "process_on_server": "/api/library/process/server",
            "stop_processing": "/api/library/process/stop",
            "processing_progress": "/api/library/progress",
            "worker_register": "/workers/register",
            "worker_get_job": "/workers/get_job",
            "worker_submit_result": "/workers/submit_result",
            "similar_by_track": "/similar/by_track/{track_id}",
            "compute_on_server": "/compute/on_server"
        }
    }


@app.get("/api/library/stats", response_model=LibraryStatsResponse)
async def get_library_stats():
    """Get statistics about the current music library database."""
    try:
        stats = service.get_database_stats()
        return LibraryStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search/text", response_model=List[SearchResultResponse])
async def search_by_text(search_request: SearchRequest):
    """Search for music tracks by text description."""
    try:
        results = service.search_similar_by_text(
            search_request.query, 
            search_request.n_results
        )
        
        return [
            SearchResultResponse(
                track=TrackResponse(
                    artist=result.track.artist,
                    album=result.track.album,
                    title=result.track.title,
                    filepath=str(result.track.filepath),
                    plex_rating_key=result.track.plex_rating_key
                ),
                similarity_score=result.similarity_score,
                distance=result.distance
            )
            for result in results
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search/text", response_model=List[SearchResultResponse])
async def search_by_text_get(
    q: str = Query(..., description="Search query"),
    n_results: int = Query(10, description="Number of results to return")
):
    """Search for music tracks by text description (GET endpoint)."""
    try:
        results = service.search_similar_by_text(q, n_results)
        
        return [
            SearchResultResponse(
                track=TrackResponse(
                    artist=result.track.artist,
                    album=result.track.album,
                    title=result.track.title,
                    filepath=str(result.track.filepath),
                    plex_rating_key=result.track.plex_rating_key
                ),
                similarity_score=result.similarity_score,
                distance=result.distance
            )
            for result in results
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search/audio", response_model=List[SearchResultResponse])
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
        
        # Create temporary file to store upload
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as temp_file:
            content = await audio.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        logger.info(f"Audio file saved to temporary location: {temp_file_path}")
        
        try:
            # Search using temporary file
            results = service.search_similar_by_audio(Path(temp_file_path), n_results)
            logger.info(f"Audio search completed successfully - found {len(results)} results")
            
            return [
                SearchResultResponse(
                    track=TrackResponse(
                        artist=result.track.artist,
                        album=result.track.album,
                        title=result.track.title,
                        filepath=str(result.track.filepath),
                        plex_rating_key=result.track.plex_rating_key
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
                logger.debug(f"Cleaned up temporary file: {temp_file_path}")
            except OSError as e:
                logger.warning(f"Failed to clean up temporary file {temp_file_path}: {e}")
                
    except HTTPException:
        # Re-raise HTTP exceptions as they are
        raise
    except Exception as e:
        logger.error(f"Audio search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Audio search failed: {str(e)}")


@app.get("/api/library/tracks", response_model=TracksListResponse)
async def get_library_tracks(
    page: int = Query(1, ge=1, description="Page number (starting from 1)"),
    limit: int = Query(50, ge=1, le=200, description="Number of tracks per page"),
    search: Optional[str] = Query(None, description="Search query for filtering tracks")
):
    """Get tracks from the library with pagination and optional search."""
    logger.info(f"Library tracks request - page: {page}, limit: {limit}, search: {search}")
    
    try:
        if search and search.strip():
            # Use search functionality
            logger.info(f"Performing library search for: '{search.strip()}'")
            tracks = service.search_tracks_in_database(search.strip(), limit=limit, offset=(page - 1) * limit)
            total_count = service.count_tracks_in_database(search.strip())
        else:
            # Regular pagination
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
                    plex_rating_key=track.plex_rating_key
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
            "client": {
                "server_host": config.client.server_host,
                "server_port": config.client.server_port
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
    """Save configuration to YAML file."""
    try:
        logger.info("Configuration save request received")
        # Import the YAML config manager
        from ..config_yaml import MyceliumConfig as ConfigYAML
        
        # Create new config object with updated values - map the fields correctly
        from ..config_yaml import PlexConfig, CLAPConfig, ChromaConfig, DatabaseConfig, APIConfig, ClientConfig, LoggingConfig
        
        plex_config = PlexConfig(**config_request.plex)
        clap_config = CLAPConfig(**config_request.clap)
        chroma_config = ChromaConfig(**config_request.chroma)
        database_config = DatabaseConfig()
        api_config = APIConfig(**config_request.api)
        client_config = ClientConfig(**config_request.client)
        logging_config = LoggingConfig(**config_request.logging)
        
        yaml_config = ConfigYAML(
            plex=plex_config,
            clap=clap_config,
            chroma=chroma_config,
            database=database_config,
            api=api_config,
            client=client_config,
            logging=logging_config
        )
        
        # Save to default YAML location
        yaml_config.save_to_yaml()
        logger.info("Configuration saved successfully to YAML file")
        
        return {
            "message": "Configuration saved successfully. Restart the server to apply changes.",
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Failed to save configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save configuration: {str(e)}")


@app.post("/api/library/scan")
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
async def get_processing_progress():
    """Get current processing progress and statistics."""
    try:
        stats = service.get_processing_progress()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Worker Coordination API
@app.post("/workers/register", response_model=WorkerRegistrationResponse)
async def register_worker(request: WorkerRegistrationRequest):
    """Register a worker with the server."""
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
    try:
        task = job_queue.get_next_job(worker_id)
        if task is None:
            # No job available - return 204 No Content
            logger.debug(f"No job available for worker {worker_id}")
            return None
        
        logger.info(f"Assigning task {task.task_id} to worker {worker_id} for track {task.track_id}")
        return JobRequest(
            task_id=task.task_id,
            task_type=task.task_type,
            track_id=task.track_id,
            download_url=task.download_url
        )
    except Exception as e:
        logger.error(f"Error getting job for worker {worker_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/workers/submit_result", response_model=TaskResultResponse)
async def submit_result(request: TaskResultRequest):
    """Submit the result of a completed task."""
    try:
        logger.info(f"Worker result submission for task {request.task_id}, track {request.track_id}, status: {request.status}")
        
        task_result = TaskResult(
            task_id=request.task_id,
            track_id=request.track_id,
            status=request.status,
            embedding=request.embedding,
            error_message=request.error_message
        )
        
        success = job_queue.submit_result(task_result)
        logger.info(f"Task result submission: success={success}")
        
        if success and request.embedding:
            # Save embedding to ChromaDB
            logger.info(f"Saving worker-generated embedding for track {request.track_id}, size: {len(request.embedding)}")
            service.save_embedding(request.track_id, request.embedding)
            logger.info(f"Successfully saved worker-generated embedding for track {request.track_id}")
        elif request.error_message:
            logger.error(f"Worker task failed for track {request.track_id}: {request.error_message}")
        
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
                        plex_rating_key=result.track.plex_rating_key
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
            download_url = f"http://{config.api.host}:{config.api.port}/download_track/{track_id}"
            task = job_queue.create_task(track_id, download_url)
            
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
    
    except HTTPException:
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


@app.get("/api/queue/task/{task_id}")
async def get_task_status(task_id: str):
    """Get status of a specific task."""
    try:
        task = job_queue.get_task_status(task_id)
        if task:
            return {
                "task_id": task.task_id,
                "status": task.status.value,
                "track_id": task.track_id,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "error_message": task.error_message
            }
        else:
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
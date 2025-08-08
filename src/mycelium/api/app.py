"""FastAPI application for Mycelium web interface."""

from pathlib import Path
from typing import List

import uvicorn
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .worker_models import (
    WorkerRegistrationRequest, WorkerRegistrationResponse,
    JobRequest, TaskResultRequest, TaskResultResponse,
    ConfirmationRequiredResponse, ComputeOnServerRequest,
    QueueStatsResponse
)
from ..application.job_queue import JobQueueService
from ..application.services import MyceliumService
from ..config import MyceliumConfig
from ..domain.worker import TaskResult


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


class LibraryStatsResponse(BaseModel):
    total_embeddings: int
    collection_name: str
    database_path: str


class SearchRequest(BaseModel):
    query: str
    n_results: int = 10


# Initialize configuration and service
config = MyceliumConfig.from_env()

# Validate Plex token
if not config.plex.token:
    raise ValueError("PLEX_TOKEN environment variable is required")

# Initialize the main service
service = MyceliumService(
    plex_url=config.plex.url,
    plex_token=config.plex.token,
    music_library_name=config.plex.music_library_name,
    db_path=config.chroma.db_path,
    collection_name=config.chroma.collection_name,
    model_id=config.clap.model_id
)

# Initialize job queue service
job_queue = JobQueueService()

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
            "search_text": "/api/search/text",
            "scan_library": "/api/library/scan",
            "process_library": "/api/library/process",
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


@app.post("/api/library/scan")
async def scan_library():
    """Scan the Plex music library."""
    try:
        tracks = service.scan_library()
        return {
            "message": f"Successfully scanned library",
            "tracks_found": len(tracks),
            "sample_tracks": [
                {
                    "artist": track.artist,
                    "title": track.title,
                    "album": track.album
                }
                for track in tracks[:5]  # First 5 tracks as sample
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/library/process")
async def process_library():
    """Run the full library processing workflow (scan, generate embeddings, index)."""
    try:
        # This is a long-running operation, in production you'd want to run this async
        service.full_library_processing()
        stats = service.get_database_stats()
        return {
            "message": "Library processing completed successfully",
            "stats": stats
        }
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
            return None
        
        return JobRequest(
            task_id=task.task_id,
            task_type=task.task_type,
            track_id=task.track_id,
            download_url=task.download_url
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/workers/submit_result", response_model=TaskResultResponse)
async def submit_result(request: TaskResultRequest):
    """Submit the result of a completed task."""
    try:
        task_result = TaskResult(
            task_id=request.task_id,
            track_id=request.track_id,
            status=request.status,
            embedding=request.embedding,
            error_message=request.error_message
        )
        
        success = job_queue.submit_result(task_result)
        
        if success and request.embedding:
            # Save embedding to ChromaDB
            service.save_embedding(request.track_id, request.embedding)
        
        return TaskResultResponse(
            success=success,
            message="Result submitted successfully" if success else "Task not found"
        )
    except Exception as e:
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
    try:
        # Check if embedding already exists
        if service.has_embedding(track_id):
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
        
        # Check if there are active workers
        active_workers = job_queue.get_active_workers()
        if active_workers:
            # Create task and wait for completion
            download_url = f"http://{config.api.host}:{config.api.port}/download_track/{track_id}"
            task = job_queue.create_task(track_id, download_url)
            
            # Wait for task completion (with timeout)
            completed_task = job_queue.wait_for_task_completion(task.task_id, timeout_seconds=300)
            if completed_task and completed_task.status.value == "success":
                # Task completed successfully, perform search
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
            else:
                raise HTTPException(status_code=500, detail="Task failed or timed out")
        
        # No active workers - return confirmation required
        return ConfirmationRequiredResponse(
            status="confirmation_required",
            message="The sonic signature for this song needs to be calculated, and no workers are active. Do you wish to continue on the server hardware?",
            track_id=track_id
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def compute_on_server_background(track_id: str):
    """Background task for server-side computation."""
    try:
        # Load track info
        track_info = service.get_track_by_id(track_id)
        if not track_info:
            return
        
        # Compute embedding on CPU
        embedding = service.compute_embedding_cpu(track_info.filepath)
        
        # Save to database
        service.save_embedding(track_id, embedding)
        
    except Exception as e:
        print(f"Error computing embedding on server: {e}")


@app.post("/compute/on_server")
async def compute_on_server(request: ComputeOnServerRequest, background_tasks: BackgroundTasks):
    """Compute embedding on server CPU after user confirmation."""
    try:
        # Add background task
        background_tasks.add_task(compute_on_server_background, request.track_id)
        
        return {
            "message": "Computation started in background",
            "track_id": request.track_id,
            "estimated_time": "unknown"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/queue/stats", response_model=QueueStatsResponse)
async def get_queue_stats():
    """Get job queue statistics."""
    try:
        stats = job_queue.get_queue_stats()
        return QueueStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(
        "mycelium.api.app:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.reload
    )
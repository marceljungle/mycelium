"""FastAPI application for Mycelium web interface."""

from typing import List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..application.services import MyceliumService
from ..config import MyceliumConfig


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

# Create FastAPI app
app = FastAPI(
    title="Mycelium API",
    description="Plex music collection and recommendation system using CLAP embeddings",
    version="0.1.0"
)

# Add CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js default port
    allow_credentials=True,
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
            "process_library": "/api/library/process"
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "mycelium.api.app:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.reload
    )
# Mycelium Development Instructions

**ALWAYS follow these instructions first. Only use additional search or commands if the information here is incomplete or found to be in error.**

Mycelium is a Python-based music recommendation system with AI-powered embeddings that connects to Plex media servers. It features a Python backend with FastAPI, a Next.js frontend, and uses CLAP (Contrastive Language-Audio Pre-training) for semantic music search.

## Code Style and Standards

### Python Code Standards
- **Type Hints**: All functions must include complete type hints using Python 3.9+ syntax
- **Docstrings**: Use Google-style docstrings for all classes, methods, and modules
- **Error Handling**: Use specific exception types, avoid bare `except:` clauses
- **Logging**: Use structured logging via the configured logger, never `print()` statements
- **Imports**: Group imports (standard library, third-party, local) with `isort`
- **Line Length**: Maximum 88 characters (Black formatter standard)
- **Dataclasses**: Prefer `@dataclass` for simple data containers over manual `__init__`

```python
# Good example
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

@dataclass
class Track:
    """Represents a music track from Plex.
    
    Args:
        artist: The track artist name
        title: The track title
        filepath: Path to the audio file
    """
    artist: str
    title: str
    filepath: Path
    plex_rating_key: str
    
    def validate(self) -> None:
        """Validate track data integrity."""
        if not self.artist.strip():
            raise ValueError("Artist name cannot be empty")
        logger.debug(f"Validated track: {self.display_name}")
```

### TypeScript/React Standards
- **Strict TypeScript**: Use strict mode, no `any` types without explicit reasoning
- **Component Props**: Define explicit interfaces for all component props
- **Error Boundaries**: Wrap potentially failing components in error boundaries
- **State Management**: Use React hooks patterns, avoid class components
- **Async Operations**: Use proper loading/error states for all API calls
- **Accessibility**: Include ARIA labels and semantic HTML elements

```tsx
// Good example
interface SearchResultsProps {
  tracks: Track[];
  isLoading: boolean;
  error: string | null;
  onTrackSelect: (track: Track) => void;
}

export default function SearchResults({ 
  tracks, 
  isLoading, 
  error, 
  onTrackSelect 
}: SearchResultsProps) {
  if (error) {
    return (
      <div role="alert" className="error-container">
        <p>Error: {error}</p>
      </div>
    );
  }
  
  if (isLoading) {
    return <div aria-label="Loading results">Loading...</div>;
  }
  
  return (
    <div role="list" className="search-results">
      {tracks.map(track => (
        <TrackItem 
          key={track.plex_rating_key}
          track={track}
          onClick={() => onTrackSelect(track)}
        />
      ))}
    </div>
  );
}
```

### Git Workflow
- **Branch Naming**: Use format `feature/issue-description` or `fix/issue-description`
- **Commit Messages**: Follow conventional commits format: `type(scope): description`
- **PR Requirements**: Include description, link to issue, test evidence
- **Code Review**: All changes require review, no direct pushes to main

```bash
# Example commit messages
feat(search): add audio file upload functionality
fix(api): handle timeout errors in CLAP model loading
docs(readme): update installation instructions
refactor(database): extract track repository interface
```

## Architecture Guidelines

### Clean Architecture Implementation
The project follows clean architecture with clear separation of concerns:

- **Domain Layer** (`src/mycelium/domain/`): Core business logic, no external dependencies
- **Application Layer** (`src/mycelium/application/`): Use cases and orchestration logic
- **Infrastructure Layer** (`src/mycelium/infrastructure/`): External service adapters
- **API Layer** (`src/mycelium/api/`): Web interface and endpoint definitions

### Dependency Injection Pattern
```python
# Repository interface in domain layer
class TrackRepository(ABC):
    @abstractmethod
    async def save_track(self, track: Track) -> None: ...

# Implementation in infrastructure layer  
class SqliteTrackRepository(TrackRepository):
    def __init__(self, db_path: str): ...

# Injection in application layer
class TrackScanningUseCase:
    def __init__(self, track_repo: TrackRepository, plex_client: PlexClient):
        self._track_repo = track_repo
        self._plex_client = plex_client
```

### Error Handling Patterns
- **Domain Exceptions**: Create specific exception types for business logic errors
- **Graceful Degradation**: Handle external service failures gracefully
- **Logging Context**: Include relevant context in error logs
- **User-Friendly Messages**: Translate technical errors to user-readable messages

```python
class PlexConnectionError(Exception):
    """Raised when unable to connect to Plex server."""
    pass

class TrackProcessingError(Exception):
    """Raised when track processing fails."""
    def __init__(self, track_path: str, reason: str):
        self.track_path = track_path
        super().__init__(f"Failed to process {track_path}: {reason}")
```

## Testing Strategy

### Test Organization
- **Unit Tests**: Test individual functions/methods in isolation
- **Integration Tests**: Test component interactions (API endpoints, database operations)
- **End-to-End Tests**: Test complete user workflows via web interface
- **Property-Based Testing**: Use hypothesis for complex data validation

### Python Testing
```python
# Example unit test structure
import pytest
from unittest.mock import Mock, patch
from mycelium.domain.models import Track
from mycelium.application.use_cases import TrackScanningUseCase

class TestTrackScanningUseCase:
    @pytest.fixture
    def mock_track_repo(self):
        return Mock()
    
    @pytest.fixture  
    def mock_plex_client(self):
        return Mock()
    
    @pytest.fixture
    def use_case(self, mock_track_repo, mock_plex_client):
        return TrackScanningUseCase(mock_track_repo, mock_plex_client)
    
    async def test_scan_saves_discovered_tracks(self, use_case, mock_track_repo, mock_plex_client):
        # Given
        mock_tracks = [Track(artist="Test", title="Song", filepath=Path("/test.mp3"), plex_rating_key="123")]
        mock_plex_client.get_tracks.return_value = mock_tracks
        
        # When
        result = await use_case.scan_library()
        
        # Then
        assert result.tracks_found == 1
        mock_track_repo.save_track.assert_called_once_with(mock_tracks[0])
```

### Frontend Testing
```tsx
// Example component test
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import SearchInterface from '@/components/SearchInterface';

describe('SearchInterface', () => {
  it('should submit search when form is submitted', async () => {
    const mockOnSearch = vi.fn();
    render(<SearchInterface onSearch={mockOnSearch} />);
    
    const input = screen.getByLabelText(/search/i);
    const button = screen.getByRole('button', { name: /search/i });
    
    fireEvent.change(input, { target: { value: 'jazz music' } });
    fireEvent.click(button);
    
    await waitFor(() => {
      expect(mockOnSearch).toHaveBeenCalledWith('jazz music');
    });
  });
});
```

### Test Data Management
- **Fixtures**: Use pytest fixtures for reusable test data
- **Factories**: Create test data factories for complex objects
- **Database**: Use in-memory SQLite for fast test database operations
- **Mocking**: Mock external services (Plex API, CLAP models) in tests

### API Development Best Practices
- **Request/Response Models**: Use Pydantic models for all API inputs/outputs
- **Error Handling**: Return appropriate HTTP status codes with structured error responses
- **Async/Await**: Use async endpoints for I/O operations (database, external APIs)
- **Validation**: Validate all inputs at the API boundary
- **Documentation**: Use FastAPI automatic OpenAPI documentation
- **Rate Limiting**: Consider rate limiting for expensive operations

```python
# Good API endpoint example
from fastapi import HTTPException, status
from pydantic import BaseModel, validator

class SearchRequest(BaseModel):
    query: str
    limit: int = 20
    
    @validator('query')
    def query_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Query cannot be empty')
        return v.strip()

class SearchResponse(BaseModel):
    tracks: List[TrackResponse]
    total_results: int
    query_time_ms: float

@app.post("/api/search/text", response_model=SearchResponse)
async def search_tracks(request: SearchRequest, service: MyceliumService = Depends()):
    try:
        start_time = time.time()
        results = await service.search_by_text(request.query, limit=request.limit)
        query_time = (time.time() - start_time) * 1000
        
        return SearchResponse(
            tracks=[TrackResponse.from_domain(track) for track in results],
            total_results=len(results),
            query_time_ms=query_time
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Search failed")
```

### Performance Considerations
- **Async Programming**: Use async/await for I/O-bound operations
- **Connection Pooling**: Implement connection pooling for database operations
- **Caching**: Cache expensive computations (embeddings, search results)
- **Batch Processing**: Process multiple items together when possible
- **Resource Management**: Properly close files, database connections, and HTTP sessions

### Security Guidelines
- **Input Validation**: Sanitize all user inputs to prevent injection attacks
- **Path Traversal**: Validate file paths to prevent directory traversal
- **Authentication**: Implement proper authentication for API endpoints if needed
- **Secrets Management**: Never commit secrets, use environment variables or secure vaults
- **CORS**: Configure CORS appropriately for frontend-backend communication


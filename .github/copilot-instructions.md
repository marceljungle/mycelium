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

## Project Structure and Development Patterns

### Directory Organization
```
mycelium/
├── src/mycelium/           # Python backend (clean architecture)
│   ├── domain/             # Core business logic and models (no external deps)
│   │   ├── models.py       # Domain entities (Track, Playlist, etc.)
│   │   ├── repositories.py # Repository interfaces  
│   │   └── worker.py       # Worker domain logic
│   ├── application/        # Use cases and orchestration
│   │   ├── services.py     # Main application service
│   │   ├── search_use_cases.py    # Music search use case implementations
│   │   ├── library_management_use_cases.py  # Library scanning and processing workflows
│   │   └── job_queue.py    # Worker coordination and task distribution
│   ├── infrastructure/     # External service adapters
│   │   ├── plex_adapter.py     # Plex API integration
│   │   ├── clap_adapter.py     # CLAP model integration
│   │   ├── chroma_adapter.py   # Vector database operations
│   │   └── track_database.py   # Track metadata database
│   ├── api/                # FastAPI web endpoints
│   │   ├── app.py          # Main API application and routes
│   │   └── worker_models.py # Worker-specific API models
│   ├── config.py           # Configuration management
│   ├── main.py             # CLI entry point with Typer
│   └── client.py           # GPU worker client for distributed processing
├── frontend/               # Next.js frontend (TypeScript + Tailwind)
│   ├── src/app/            # Next.js app router pages
│   ├── src/components/     # React components
│   │   ├── Navigation.tsx      # Main navigation system
│   │   ├── SearchInterface.tsx # Text + audio search interface
│   │   ├── LibraryPage.tsx     # Library browsing and management
│   │   ├── SettingsPage.tsx    # Configuration UI
│   │   └── LibraryStats.tsx    # Statistics and operations UI
│   ├── src/config/         # Frontend configuration
│   └── src/contexts/       # React context providers
├── config.example.yml      # Configuration template
├── pyproject.toml          # Python project configuration
└── requirements.txt        # Python dependencies (for compatibility)
```

### Component Development Patterns

#### React Components
- **Single Responsibility**: Each component should have one clear purpose
- **Props Drilling**: Avoid deep prop drilling, use context for shared state
- **Error Boundaries**: Wrap components that might fail in error boundaries
- **Loading States**: Always handle loading and error states explicitly
- **Accessibility**: Use semantic HTML and ARIA attributes

#### Python Modules
- **Repository Pattern**: Use repository interfaces for data access
- **Service Layer**: Orchestrate use cases in service classes
- **Dependency Injection**: Inject dependencies through constructors
- **Factory Pattern**: Use factories for complex object creation

### File Naming Conventions
- **Python Files**: Use snake_case (e.g., `track_repository.py`)
- **TypeScript Files**: Use PascalCase for components (e.g., `SearchInterface.tsx`)
- **Test Files**: Mirror source structure with `test_` prefix (e.g., `test_track_repository.py`)
- **Configuration**: Use kebab-case for config files (e.g., `eslint.config.mjs`)

### Import Organization
```python
# Python imports order:
# 1. Standard library
import logging
from pathlib import Path
from typing import List, Optional

# 2. Third-party packages  
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 3. Local application imports
from mycelium.domain.models import Track
from mycelium.infrastructure.track_database import TrackDatabase
```

```tsx
// TypeScript imports order:
// 1. React and Next.js
import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

// 2. Third-party packages
import { z } from 'zod';

// 3. Local imports (absolute paths using @/)
import { API_BASE_URL } from '@/config/api';
import { Track } from '@/types/models';
import { SearchResults } from '@/components/SearchResults';
```

## Code Quality and CI

### Linting and Formatting
```bash
# Python code quality (run in order)
black src/                   # Code formatting
isort src/                   # Import sorting  
mypy src/                    # Type checking
# pylint src/                # Optional: comprehensive linting

# Frontend code quality
cd frontend
npm run lint                 # ESLint + TypeScript checking
npm run lint -- --fix       # Auto-fix linting issues
npm run build                # Verify build succeeds
```

### Pre-commit Workflow
1. **Always run linters** before committing changes
2. **Frontend build must pass** - `npm run build` should succeed without errors
3. **Type checking** - Both `mypy` (Python) and `tsc` (TypeScript) should pass
4. **Test relevant functionality** manually if no automated tests exist
5. **Review diff** - Ensure only intended changes are included

### Code Review Checklist
When reviewing PRs, check for:
- [ ] Type hints on all Python functions
- [ ] Proper error handling and logging
- [ ] Input validation on API endpoints
- [ ] React components have proper TypeScript interfaces
- [ ] No hardcoded values (use configuration)
- [ ] Async/await used correctly for I/O operations
- [ ] Database connections properly closed
- [ ] User-facing error messages are clear and helpful

### Performance Monitoring
- **Profile long-running operations** (embedding generation, large searches)
- **Monitor memory usage** during batch processing
- **Log timing information** for critical paths
- **Use database query analysis** for optimization opportunities

### Documentation Standards
- **Python**: Google-style docstrings for all public functions/classes
- **TypeScript**: JSDoc comments for complex functions
- **API**: OpenAPI/Swagger documentation via FastAPI
- **README**: Keep setup and usage instructions current
- **Changelog**: Document breaking changes and new features

```python
# Good documentation example
async def search_by_text(
    self, 
    query: str, 
    limit: int = 20
) -> List[SearchResult]:
    """Search for tracks using text description.
    
    Uses CLAP model to encode the text query and performs similarity
    search against stored track embeddings.
    
    Args:
        query: Natural language description of desired music
        limit: Maximum number of results to return
        
    Returns:
        List of search results ordered by similarity score
        
    Raises:
        ValueError: If query is empty or limit is invalid
        CLAPModelError: If text encoding fails
        DatabaseError: If vector search fails
    """
```

## Development Environment Setup

### Critical Setup Notes
**IMPORTANT: Set long timeouts for installation commands - ML dependencies take 15-45 minutes to install.**

1. **Python Backend Setup:**
   ```bash
   # Install with extended timeout due to PyTorch, transformers
   pip install --timeout 600 --retries 5 -e .
   ```
   - **Expected time**: 15-45 minutes (torch ~2GB, transformers ~500MB)
   - **Network issues**: May fail in CI environments due to PyPI connectivity

2. **Frontend Setup:**
   ```bash
   cd frontend
   npm install              # ~90 seconds
   npm run dev             # Start development server
   ```

3. **Configuration:**
   ```bash
   # YAML configuration (required)
   mkdir -p ~/.config/mycelium
   cp config.example.yml ~/.config/mycelium/config.yml
   # Edit config.yml with your Plex token
   ```

### Development Workflow
```bash
# Start full development environment
mycelium server             # Backend + Frontend combined (recommended)

# Alternative: Run separately  
mycelium server --backend-only &
cd frontend && npm run dev  

# Distributed processing (optional)
mycelium client --server-host 192.168.1.100  # On GPU machine
```

### Build and Testing
```bash
# Frontend build (must succeed)
cd frontend
npm run lint                # Fix linting errors first
npm run build              # 5-15 seconds if successful

# Backend testing (when dependencies installed)
mycelium server &          # Start server for testing
curl http://localhost:8000/api/library/stats  # Test API

# End-to-end testing
# 1. Open http://localhost:8000
# 2. Verify UI loads correctly
# 3. Test search functionality  
# 4. Test library operations
```

## API Reference

### Core Endpoints
```bash
# Library Management
POST /api/library/scan          # Scan Plex library
POST /api/library/process       # Process embeddings (resumable)
GET  /api/library/stats         # Database statistics
GET  /api/library/progress      # Processing progress

# Search Operations  
POST /api/search/text          # Text-based search
POST /api/search/audio         # Audio file search
GET  /api/search/text?q=query  # Quick text search

# Configuration
GET  /api/config               # Get current config
POST /api/config               # Update configuration

# Worker Coordination (for distributed processing)
POST /workers/register         # Register worker
GET  /workers/get_job          # Get processing job
POST /workers/submit_result    # Submit job result
```

## Dependencies and System Requirements

### Runtime Requirements
- **Python 3.9+ (tested with 3.12)**
- **Node.js 18+ (tested with 20.19)**  
- **Plex Media Server** with music library
- **GPU recommended** for faster embedding generation

### Key Python Dependencies
- `torch>=2.0.0` - Deep learning framework (~2GB)
- `transformers>=4.30.0` - Hugging Face models (~500MB) 
- `librosa>=0.10.0` - Audio processing
- `chromadb>=0.4.0` - Vector database
- `fastapi>=0.100.0` - Web framework
- `plexapi>=4.15.0` - Plex integration

### Frontend Dependencies
- `next@15.4.5` - React framework
- `react@19.1.0` - UI library
- `typescript@^5` - Type checking
- `tailwindcss@^4` - CSS framework

## Troubleshooting and Common Issues

### Development Issues
- **Module not found**: Ensure `pip install -e .` completed successfully
- **Frontend build fails**: Run `npm run lint` first, check for TypeScript errors
- **API connection errors**: Verify server is running with `mycelium server`
- **Plex connection issues**: Check token in `~/.config/mycelium/config.yml`

### Network and Infrastructure Issues
- **PyPI timeouts**: Use `pip install --timeout 600 --retries 5 -e .`
- **Google Fonts errors**: Frontend build may fail in restricted networks
- **CLAP model downloads**: ~1GB download on first use, may be slow

### Performance Optimization
- **Use GPU workers** for large libraries (distributed processing)
- **Configure batch sizes** based on available memory
- **Monitor processing** via web interface or API endpoints
- **Resume interrupted processing** - embeddings generation is resumable

### Configuration Setup
- **Configuration**: YAML-only at `~/.config/mycelium/config.yml` (auto-generated on first run)
- **Data storage**: Platform-specific directories (see config for paths)
- **Setup**: Edit the auto-generated config file with your Plex token
- **Note**: Environment variable support has been removed (despite README mentioning it)

## Quick Reference Commands

```bash
# Complete setup from scratch
pip install --timeout 600 --retries 5 -e .  # 15-45 min
cd frontend && npm install                   # 1.5 min

# Configuration setup
mkdir -p ~/.config/mycelium && cp config.example.yml ~/.config/mycelium/config.yml
# Edit ~/.config/mycelium/config.yml and add your Plex token

# Development workflow  
cd frontend && npm run dev          # Start frontend only
mycelium server                     # Start backend + frontend (recommended)

# Distributed processing (recommended)
mycelium client --server-host 192.168.1.100  # Start GPU worker

# Validation
cd frontend && npm run lint         # Frontend linting
cd frontend && npm run build        # Frontend build test
mycelium server                     # Start server and test web interface
```
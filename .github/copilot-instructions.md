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

- **Domain Layer** (`backend/mycelium/domain/`): Core business logic, no external dependencies
- **Application Layer** (`backend/mycelium/application/`): Use cases and orchestration logic
- **Infrastructure Layer** (`backend/mycelium/infrastructure/`): External service adapters
- **API Layer** (`backend/mycelium/api/`): Web interface and endpoint definitions

### API Types — Single Source of Truth
All API types are **hand-written** — no code generation.

- **Python DTOs**: `backend/mycelium/api/schemas.py` (Pydantic v2)
- **TypeScript types**: `frontend/src/server_api/types.ts` and `frontend/src/worker_api/types.ts`
- **API clients**: `frontend/src/server_api/client.ts` and `frontend/src/worker_api/client.ts` (typed `fetch` wrappers)

#### Workflow for API Changes:
1. **Update Python DTOs**: Edit `backend/mycelium/api/schemas.py`
2. **Update TypeScript types**: Edit `frontend/src/server_api/types.ts` (or `worker_api/types.ts`)
3. **Update FastAPI endpoints**: Modify `app.py` or `client_app.py` to implement changes
4. **Update frontend client**: Add/modify methods in `client.ts` if new endpoints are added

#### Key Points:
- **Python DTOs are hand-written** — Import from `mycelium.api.schemas` (Pydantic v2 native)
- **TypeScript types are hand-written** — Import from `@/server_api/client` or `@/worker_api/client`

```python
# Correct: Use hand-written DTOs in FastAPI endpoints
from mycelium.api.schemas import (
    LibraryStatsResponse,
    SearchResultResponse,
)

@app.get("/api/library/stats", response_model=LibraryStatsResponse)
async def get_library_stats():
    stats = service.get_database_stats()
    return LibraryStatsResponse(**stats)
```

### Model Registry
To add a new embedding model, only two changes are needed:
1. Create an adapter in `infrastructure/model/` implementing `EmbeddingGenerator`
2. Add one entry to `MODEL_REGISTRY` in `application/embedding/registry.py`

The factory, config validation, and CLI will pick it up automatically.

### Dual Frontend Architecture
The project has **TWO separate frontend builds** from the same source:

1. **Server Frontend** (port 8000):
   - Built with `API_BASE_URL=/api` (relative URLs)
   - Served from `backend/mycelium/frontend_dist/`
   - Uses server API client (`@/server_api/client`)
   - Shows server configuration and full library management

2. **Client/Worker Frontend** (port 3001 by default, configurable):
   - Built with `API_BASE_URL=http://localhost:3001/api` (absolute URLs)
   - Served from `backend/mycelium/client_frontend_dist/`
   - Uses worker API client (`@/worker_api/client`)
   - Shows only worker configuration (lighter interface)

```bash
# Build both frontends
./build.sh                          # Builds both frontends
./build_frontend.sh                 # Server frontend only
./build_client_frontend.sh          # Worker frontend only

# Build with Python wheel
./build.sh --with-wheel             # Full build including packaging
```

### Configuration Architecture
The project uses **two separate YAML configurations**:

1. **Server Config** (`~/.config/mycelium/config.yml`):
   - Loaded by `MyceliumConfig` in `config.py`
   - Contains: Plex, API, CLAP, ChromaDB, Server, Database, Logging
   - Used by: `mycelium-ai server` command
   - Hot-reloadable via `/api/config` POST endpoint

2. **Client Config** (`~/.config/mycelium/client_config.yml`):
   - Loaded by `MyceliumClientConfig` in `client_config.py`
   - Contains: CLAP, Client, ClientAPI, Logging
   - Used by: `mycelium-ai client` command
   - Hot-reloadable via worker API `/api/config` POST endpoint

```python
# Server configuration
from mycelium.config import MyceliumConfig
config = MyceliumConfig.load_from_yaml()
config.setup_logging()

# Client configuration
from mycelium.client_config import MyceliumClientConfig
client_config = MyceliumClientConfig.load_from_yaml()
client_config.setup_logging()
```

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
- **Request/Response Models**: Use hand-written Pydantic v2 DTOs from `api/schemas.py`
- **Error Handling**: Return appropriate HTTP status codes with structured error responses
- **Async/Await**: Use async endpoints for I/O operations (database, external APIs)
- **Validation**: Validation is handled automatically by Pydantic models
- **Documentation**: FastAPI auto-generates OpenAPI docs from Pydantic models at `/docs`
- **Rate Limiting**: Consider rate limiting for expensive operations

```python
# Correct: Use hand-written DTOs in FastAPI endpoints
from mycelium.api.schemas import (
    SearchResultResponse,
    LibraryStatsResponse,
)

@app.get("/api/library/stats", response_model=LibraryStatsResponse)
async def get_library_stats():
    """Get statistics about the current music library database."""
    try:
        stats = service.get_database_stats()
        return LibraryStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Failed to get library stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
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
├── backend/mycelium/           # Python backend (clean architecture)
│   ├── domain/             # Core business logic and models (no external deps)
│   │   ├── models.py       # Domain entities (Track, Playlist, etc.)
│   │   ├── repositories.py # Repository interfaces  
│   │   └── worker.py       # Worker domain logic
│   ├── application/        # Use cases and orchestration
│   │   ├── services.py     # Main application service
│   │   ├── search/         # Music search use cases
│   │   │   └── use_cases.py
│   │   ├── library/        # Library scanning and processing workflows
│   │   │   └── use_cases.py
│   │   ├── embedding/      # Embedding generator factory
│   │   │   └── factory.py
│   │   └── jobs/           # Worker coordination and task distribution
│   │       └── queue.py
│   ├── infrastructure/     # External service adapters
│   │   ├── plex/           # Plex API integration
│   │   │   └── adapter.py
│   │   ├── model/          # Embedding model implementations
│   │   │   ├── clap.py     # CLAP model integration
│   │   │   └── muq.py      # MuQ model integration
│   │   └── db/             # Database adapters
│   │       ├── chroma.py   # ChromaDB vector database operations
│   │       └── tracks.py   # SQLite track metadata database
│   ├── api/                # FastAPI web endpoints
│   │   ├── app.py          # Main server API application and routes
│   │   ├── client_app.py   # Worker/client API for configuration
│   │   ├── schemas.py       # Hand-written Pydantic v2 API DTOs
│   │   └── worker_models.py # Worker-specific API models
│   ├── config.py           # Server configuration management
│   ├── client_config.py    # Client/worker configuration management
│   ├── main.py             # CLI entry point with Typer
│   └── client.py           # GPU worker client for distributed processing
├── frontend/               # Next.js frontend (TypeScript + Tailwind) - TWO BUILDS
│   ├── src/app/            # Next.js app router pages
│   ├── src/components/     # React components
│   │   ├── Navigation.tsx      # Main navigation system
│   │   ├── SearchInterface.tsx # Text + audio search interface
│   │   ├── LibraryPage.tsx     # Library browsing and management
│   │   ├── SettingsPage.tsx    # Server configuration UI
│   │   ├── ClientSettingsPage.tsx # Worker configuration UI
│   │   └── LibraryStats.tsx    # Statistics and operations UI
│   ├── src/server_api/     # Server API client (hand-written)
│   │   ├── types.ts        # TypeScript types (mirrors schemas.py)
│   │   └── client.ts       # Typed fetch API client
│   ├── src/worker_api/     # Worker API client (hand-written)
│   │   ├── types.ts        # TypeScript types (mirrors schemas.py)
│   │   └── client.ts       # Typed fetch API client
│   ├── src/config/         # Frontend configuration
│   └── next.config.ts      # Next.js config (exports static build)
├── build.sh                # Orchestrator: frontends + optional wheel
├── build_frontend.sh       # Build server frontend (output: backend/mycelium/frontend_dist)
├── build_client_frontend.sh # Build worker frontend (output: backend/mycelium/client_frontend_dist)
├── build_wheel.sh          # Build Python wheel with both frontends
├── config.example.yml      # Server configuration template
├── client_config.example.yml # Worker configuration template
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
- **API Client Usage**: Import from `@/server_api/client` or `@/worker_api/client` depending on the context

#### Dual Frontend Consideration
The same React codebase is built **twice** with different API configurations:

1. **Server Frontend Build** (`build_frontend.sh`):
   - Environment: `API_BASE_URL=/api` (relative)
   - Output: `backend/mycelium/frontend_dist/`
   - Used by: `mycelium-ai server` command
   - Shows: Full UI with SettingsPage (server config)

2. **Client Frontend Build** (`build_client_frontend.sh`):
   - Environment: `API_BASE_URL=http://localhost:3001/api` (absolute)
   - Output: `backend/mycelium/client_frontend_dist/`
   - Used by: `mycelium-ai client` command
   - Shows: Minimal UI with ClientSettingsPage (worker config)

```typescript
// Frontend automatically uses correct API base URL
import { api } from '@/server_api/client';        // For server API
import { workerApi } from '@/worker_api/client';  // For worker API

// API_BASE_URL is set during build and used by API clients
// Server build: API_BASE_URL=/api
// Client build: API_BASE_URL=http://localhost:3001/api
```

**Important**: When adding new components, consider whether they should appear in:
- **Server frontend only** (e.g., SettingsPage)
- **Client frontend only** (e.g., ClientSettingsPage)  
- **Both frontends** (e.g., Navigation, common components)

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
from mycelium.infrastructure.db.tracks import TrackDatabase
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
import { api } from '@/server_api/client';        // Server API client
import { workerApi } from '@/worker_api/client';  // Worker API client
import type { Track } from '@/server_api/client';  // Generated types
import { SearchResults } from '@/components/SearchResults';
```

## Packaging and Distribution

### Build System Overview
The project uses a multi-stage build system with shell scripts:

1. **`build.sh`** - Orchestrator script:
   - Builds server frontend (`build_frontend.sh`)
   - Builds client frontend (`build_client_frontend.sh`)
   - Optionally builds Python wheel (`build_wheel.sh` with `--with-wheel` flag)

2. **`build_frontend.sh`** - Server frontend build:
   - Runs `npm run build` in frontend directory
   - Copies output to `backend/mycelium/frontend_dist/`
   - Used by server mode (port 8000)

3. **`build_client_frontend.sh`** - Worker frontend build:
   - Runs `npm run build` with different `API_BASE_URL`
   - Copies output to `backend/mycelium/client_frontend_dist/`
   - Used by client mode (port 3001)

4. **`build_wheel.sh`** - Python packaging:
   - Runs `python -m build` to create wheel
   - Includes both frontend builds in the package

### Package Contents
The Python wheel (`mycelium-ai`) includes:
- Python source code from `backend/mycelium/`
- Server frontend static files in `mycelium/frontend_dist/`
- Client frontend static files in `mycelium/client_frontend_dist/`

```toml
# pyproject.toml package data
[tool.setuptools.package-data]
mycelium = ["frontend_dist/**", "client_frontend_dist/**"]
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
6. **Keep Python and TypeScript types in sync** — when changing `schemas.py`, update `types.ts` too

### Code Review Checklist
When reviewing PRs, check for:
- [ ] Type hints on all Python functions
- [ ] Proper error handling and logging
- [ ] Input validation handled by Pydantic v2 DTOs in `api/schemas.py`
- [ ] React components have proper TypeScript interfaces
- [ ] No hardcoded values (use configuration)
- [ ] Async/await used correctly for I/O operations
- [ ] Database connections properly closed
- [ ] User-facing error messages are clear and helpful
- [ ] **Python and TypeScript types in sync** — `schemas.py` matches `types.ts`
- [ ] **Frontend uses API clients** from `@/server_api/client` or `@/worker_api/client`
- [ ] **Both frontends tested** if changes affect UI (server mode and client mode)

### Performance Monitoring
- **Profile long-running operations** (embedding generation, large searches)
- **Monitor memory usage** during batch processing
- **Log timing information** for critical paths
- **Use database query analysis** for optimization opportunities

### Documentation Standards
- **Python**: Google-style docstrings for all public functions/classes
- **TypeScript**: JSDoc comments for complex functions
- **API**: FastAPI auto-serves interactive docs at `/docs`
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
   ```

3. **Server Configuration (Required for server mode):**
   ```bash
   # YAML configuration (auto-generated on first run)
   mkdir -p ~/.config/mycelium
   cp config.example.yml ~/.config/mycelium/config.yml
   # Edit config.yml with your Plex token and settings
   ```

4. **Client Configuration (Optional, only for GPU workers):**
   ```bash
   # YAML configuration for worker mode
   cp client_config.example.yml ~/.config/mycelium/client_config.yml
   # Edit client_config.yml with server connection info
   ```

### Development Workflow
```bash
# Start full development environment
mycelium-ai server          # Backend + Frontend combined (recommended)
# Opens: http://localhost:8000 (server mode with full UI)

# Alternative: Run client worker separately  
mycelium-ai client          # GPU worker + Client API + Frontend
# Opens: http://localhost:3001 (client mode with config UI only)

# Distributed processing (recommended for large libraries)
# On main server:
mycelium-ai server

# On GPU machine(s):
mycelium-ai client          # Connects to server, processes jobs
```

### Build and Testing
```bash
# Frontend build (both frontends - must succeed)
./build.sh                  # Full build: both frontends
cd frontend
npm run lint                # Fix linting errors first
npm run build              # 5-15 seconds if successful (builds server frontend)

# Build Python wheel with both frontends
./build.sh --with-wheel     # Builds frontends and packages Python wheel

# Backend testing (when dependencies installed)
mycelium-ai server &       # Start server for testing
curl http://localhost:8000/api/library/stats  # Test API

# Worker API testing
mycelium-ai client &       # Start client for testing
curl http://localhost:3001/api/config         # Test worker config API

# End-to-end testing
# 1. Open http://localhost:8000 (server mode)
# 2. Verify UI loads correctly
# 3. Test search functionality  
# 4. Test library operations
# 5. Open http://localhost:3001 (client mode - if running worker)
# 6. Verify client config UI loads
```

## API Reference

### API Design
The API is defined by FastAPI endpoints with Pydantic v2 DTOs. FastAPI auto-generates interactive docs at `/docs`.

### Server API Endpoints (Port 8000)
```bash
# Library Management
POST /api/library/scan              # Scan Plex library
POST /api/library/process           # Process embeddings with workers (resumable)
POST /api/library/process/server    # Process embeddings on server (no workers)
POST /api/library/process/stop      # Stop processing
GET  /api/library/stats             # Database statistics
GET  /api/library/progress          # Processing progress
GET  /api/library/tracks            # List library tracks (paginated, with filters)

# Search Operations  
GET  /api/search/text               # Text-based search (?q=query)
POST /api/search/text               # Text-based search (JSON body)
POST /api/search/audio              # Audio file search

# Playlist Management
POST /api/playlists                 # Create playlist in Plex
GET  /api/playlists                 # List playlists

# Configuration
GET  /api/config                    # Get current server config
POST /api/config                    # Update server configuration (hot-reload)

# Worker Coordination (for distributed processing)
POST /workers/register              # Register worker
GET  /workers/get_job               # Get processing job
POST /workers/submit_result         # Submit job result
GET  /workers/status                # Get all workers status

# Documentation
GET  /docs                          # Interactive Swagger UI
```

### Worker API Endpoints (Port 3001 by default, configurable)
```bash
# Worker Configuration (client-side API)
GET  /api/config                    # Get current worker config
POST /api/config                    # Update worker configuration (hot-reload)
```

**Note**: The worker API port is configurable via `client_api.port` in `client_config.yml`. Default is 3001.

### Using API Clients
```typescript
// Frontend: Use hand-written TypeScript clients
import { api } from '@/server_api/client';  // Server API client
import { workerApi } from '@/worker_api/client';  // Worker API client

// Example: Search for tracks
const results = await api.searchText({ q: 'jazz piano' });

// Example: Get worker configuration
const config = await workerApi.getWorkerConfig();
```

```python
# Backend: Use hand-written Pydantic v2 DTOs
from mycelium.api.schemas import (
    SearchResultResponse,
    LibraryStatsResponse,
    WorkerConfigResponse,
)
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
- **API connection errors**: Verify server is running with `mycelium-ai server`
- **Plex connection issues**: Check token in `~/.config/mycelium/config.yml`
- **Type mismatch in frontend**: Ensure `schemas.py` and `types.ts` are in sync
- **Pydantic validation errors**: Check that DTOs in `api/schemas.py` match endpoint implementation

### Build and Deployment Issues
- **Frontend build succeeds but missing in wheel**: Run `./build.sh --with-wheel` not just `python -m build`
- **Server mode shows 404 for frontend**: Check that `backend/mycelium/frontend_dist/` exists after build
- **Client mode shows 404 for frontend**: Check that `backend/mycelium/client_frontend_dist/` exists after build
- **API endpoints return 404**: Verify FastAPI app routes are correctly defined
- **CORS errors in browser**: Check CORS middleware configuration in `app.py` or `client_app.py`

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
- **Server Configuration**: YAML at `~/.config/mycelium/config.yml` (auto-generated on first run)
- **Worker Configuration**: YAML at `~/.config/mycelium/client_config.yml` (auto-generated on first run)
- **Data storage**: Platform-specific directories (see config for paths)
- **Setup**: Edit the auto-generated config files with your Plex token (server) or server connection info (worker)
- **Hot-reload**: Both configs support hot-reloading via their respective `/api/config` POST endpoints
- **Note**: Environment variable support has been removed - use YAML only

## Quick Reference Commands

```bash
# Complete setup from scratch
pip install --timeout 600 --retries 5 -e .  # 15-45 min
cd frontend && npm install                   # 1.5 min

# Configuration setup (SERVER)
mkdir -p ~/.config/mycelium && cp config.example.yml ~/.config/mycelium/config.yml
# Edit ~/.config/mycelium/config.yml and add your Plex token

# Configuration setup (WORKER - optional, for GPU workers)
cp client_config.example.yml ~/.config/mycelium/client_config.yml
# Edit ~/.config/mycelium/client_config.yml and set server_host

# Frontend build workflow
./build.sh                  # Build both frontends
./build.sh --with-wheel     # Full build + Python packaging

# Development workflow  
mycelium-ai server                  # Start server + frontend (http://localhost:8000)
mycelium-ai client                  # Start worker + config UI (http://localhost:3001)

# Distributed processing (recommended for large libraries)
mycelium-ai server                  # On main server
mycelium-ai client                  # On GPU machine(s)

# Validation
cd frontend && npm run lint         # Frontend linting
cd frontend && npm run build        # Frontend build test (server mode)
mycelium-ai server                  # Start server and test web interface
curl http://localhost:8000/api/library/stats  # Test API
```
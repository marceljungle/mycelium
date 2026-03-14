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

### OpenAPI-First Development
**Critical**: The project uses OpenAPI specifications as the single source of truth for APIs.

#### Workflow for API Changes:
1. **Edit OpenAPI spec first**: Modify `openapi/server_openapi.yaml` or `openapi/worker_openapi.yaml`
2. **Regenerate clients**: Run `bash openapi/generate.sh` to generate:
   - TypeScript clients (`frontend/src/server_api/generated/`, `frontend/src/worker_api/generated/`)
   - Python Pydantic models (`backend/mycelium/api/generated_sources/`)
3. **Update FastAPI endpoints**: Modify `app.py` or `client_app.py` to implement changes
4. **Verify compliance**: FastAPI apps load external specs for validation
5. **Update frontend**: Use generated TypeScript types for type safety

#### Key Points:
- **Never modify generated code** - always regenerate from OpenAPI specs
- **Use generated models in FastAPI** - Import from `generated_sources.server_schemas.models` or `worker_schemas.models`
- **Frontend uses generated clients** - Import from `@/server_api/client` or `@/worker_api/client`
- **Pydantic v2 syntax** - Generated models are converted to v2 via `fix_pydantic_v2.py`

```python
# Correct: Use generated models in FastAPI endpoints
from mycelium.api.generated_sources.server_schemas.models import (
    LibraryStatsResponse,
    SearchResultResponse,
)

@app.get("/api/library/stats", response_model=LibraryStatsResponse)
async def get_library_stats():
    stats = service.get_database_stats()
    return LibraryStatsResponse(**stats)
```

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
./build.sh                          # Builds both + generates OpenAPI clients
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
- **OpenAPI-First**: Always edit OpenAPI specs first, then regenerate clients
- **Request/Response Models**: Use generated Pydantic models from `generated_sources`
- **Error Handling**: Return appropriate HTTP status codes with structured error responses
- **Async/Await**: Use async endpoints for I/O operations (database, external APIs)
- **Validation**: Validation is handled automatically by generated Pydantic models
- **Documentation**: OpenAPI specs serve as the primary documentation
- **Rate Limiting**: Consider rate limiting for expensive operations

```python
# Correct: Use generated models in FastAPI endpoints
from mycelium.api.generated_sources.server_schemas.models import (
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

### OpenAPI Client Generation Workflow

When making API changes:

```bash
# 1. Edit the OpenAPI spec
vim openapi/server_openapi.yaml  # or worker_openapi.yaml

# 2. Regenerate all clients
bash openapi/generate.sh
# This generates:
# - TypeScript clients: frontend/src/server_api/generated/ and worker_api/generated/
# - Python models: backend/mycelium/api/generated_sources/server_schemas/ and worker_schemas/

# 3. Update FastAPI endpoint implementation
vim backend/mycelium/api/app.py  # or client_app.py

# 4. Update frontend to use new types
# Generated TypeScript types are automatically available

# 5. Test the changes
mycelium-ai server &
curl http://localhost:8000/api/your/new/endpoint
```

**Important Notes**:
- Never manually edit generated code
- OpenAPI specs use Pydantic v1 generator, then converted to v2 syntax
- Generated models are in `generated_sources.server_schemas.models` and `worker_schemas.models`
- Frontend imports from `@/server_api/client` and `@/worker_api/client`
- Both FastAPI apps load external OpenAPI specs for validation

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
│   │   ├── worker_models.py # Worker-specific API models
│   │   └── generated_sources/ # OpenAPI-generated Pydantic models
│   │       ├── server_schemas/ # Server API models
│   │       └── worker_schemas/ # Worker API models
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
│   ├── src/server_api/     # Generated TypeScript client for server API
│   │   ├── client.ts       # API client wrapper
│   │   └── generated/      # OpenAPI-generated TypeScript client
│   ├── src/worker_api/     # Generated TypeScript client for worker API
│   │   ├── client.ts       # API client wrapper
│   │   └── generated/      # OpenAPI-generated TypeScript client
│   ├── src/config/         # Frontend configuration
│   └── next.config.ts      # Next.js config (exports static build)
├── openapi/                # OpenAPI-first API definitions
│   ├── server_openapi.yaml # Server API specification
│   ├── worker_openapi.yaml # Worker API specification
│   ├── generate.sh         # Generate clients from OpenAPI specs
│   ├── export_schema.py    # Export schemas from FastAPI
│   └── fix_pydantic_v2.py  # Convert Pydantic v1 to v2 syntax
├── build.sh                # Orchestrator: OpenAPI + frontends + optional wheel
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

// API_BASE_URL is set during build and used by generated clients
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
import { api } from '@/server_api/client';     // Generated server API client
import { workerApi } from '@/worker_api/client';  // Generated worker API client
import type { Track } from '@/server_api/client';  // Generated types
import { SearchResults } from '@/components/SearchResults';
```

## Packaging and Distribution

### Build System Overview
The project uses a multi-stage build system with shell scripts:

1. **`build.sh`** - Orchestrator script:
   - Runs OpenAPI client generation (`openapi/generate.sh`)
   - Builds server frontend (`build_frontend.sh`)
   - Builds client frontend (`build_client_frontend.sh`)
   - Optionally builds Python wheel (`build_wheel.sh` with `--with-wheel` flag)

2. **`openapi/generate.sh`** - OpenAPI client generation:
   - Generates TypeScript clients (server + worker) using `@openapitools/openapi-generator-cli`
   - Generates Python Pydantic models (server + worker)
   - Converts Pydantic v1 to v2 syntax using `fix_pydantic_v2.py`

3. **`build_frontend.sh`** - Server frontend build:
   - Runs `npm run build` in frontend directory
   - Copies output to `backend/mycelium/frontend_dist/`
   - Used by server mode (port 8000)

4. **`build_client_frontend.sh`** - Worker frontend build:
   - Runs `npm run build` with different `API_BASE_URL`
   - Copies output to `backend/mycelium/client_frontend_dist/`
   - Used by client mode (port 3001)

5. **`build_wheel.sh`** - Python packaging:
   - Runs `python -m build` to create wheel
   - Includes both frontend builds in the package

### Package Contents
The Python wheel (`mycelium-ai`) includes:
- Python source code from `backend/mycelium/`
- Server frontend static files in `mycelium/frontend_dist/`
- Client frontend static files in `mycelium/client_frontend_dist/`
- OpenAPI-generated Python models in `mycelium/api/generated_sources/`

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

# OpenAPI client generation (after spec changes)
bash openapi/generate.sh     # Regenerate TypeScript and Python clients
```

### Pre-commit Workflow
1. **Always run linters** before committing changes
2. **OpenAPI regeneration** if you modified `openapi/*.yaml` files
3. **Frontend build must pass** - `npm run build` should succeed without errors
4. **Type checking** - Both `mypy` (Python) and `tsc` (TypeScript) should pass
5. **Test relevant functionality** manually if no automated tests exist
6. **Review diff** - Ensure only intended changes are included
7. **Don't commit generated code separately** - generated code changes should be part of the feature commit

### Code Review Checklist
When reviewing PRs, check for:
- [ ] Type hints on all Python functions
- [ ] Proper error handling and logging
- [ ] Input validation handled by generated Pydantic models
- [ ] React components have proper TypeScript interfaces
- [ ] No hardcoded values (use configuration)
- [ ] Async/await used correctly for I/O operations
- [ ] Database connections properly closed
- [ ] User-facing error messages are clear and helpful
- [ ] **OpenAPI specs updated** if API changes were made
- [ ] **Generated clients regenerated** after OpenAPI spec changes
- [ ] **No manual edits to generated code** (files in `generated/` or `generated_sources/`)
- [ ] **Frontend uses generated API clients** from `@/server_api/client` or `@/worker_api/client`
- [ ] **Both frontends tested** if changes affect UI (server mode and client mode)

### Performance Monitoring
- **Profile long-running operations** (embedding generation, large searches)
- **Monitor memory usage** during batch processing
- **Log timing information** for critical paths
- **Use database query analysis** for optimization opportunities

### Documentation Standards
- **Python**: Google-style docstrings for all public functions/classes
- **TypeScript**: JSDoc comments for complex functions
- **API**: OpenAPI YAML specs in `openapi/` directory (source of truth)
- **README**: Keep setup and usage instructions current
- **Changelog**: Document breaking changes and new features
- **OpenAPI Specs**: Keep descriptions clear and examples accurate

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

```yaml
# Good OpenAPI documentation example (in openapi/*.yaml)
/api/search/text:
  get:
    summary: Search by text query
    description: |
      Search for tracks using natural language description.
      Uses CLAP model to encode text and find similar tracks.
    operationId: searchText
    parameters:
      - in: query
        name: q
        required: true
        schema: { type: string }
        description: Natural language search query
      - in: query
        name: limit
        schema: { type: integer, minimum: 1, maximum: 100, default: 20 }
        description: Maximum number of results
    responses:
      '200':
        description: Search results
        content:
          application/json:
            schema:
              type: array
              items:
                $ref: '#/components/schemas/SearchResultResponse'
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

5. **OpenAPI Client Generation (Required for development):**
   ```bash
   # Generate TypeScript and Python clients from OpenAPI specs
   bash openapi/generate.sh
   # Or use the full build script
   ./build.sh              # Generates clients + builds both frontends
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
# OpenAPI client generation (do this first after spec changes)
bash openapi/generate.sh    # Generates TS + Python clients from specs

# Frontend build (both frontends - must succeed)
./build.sh                  # Full build: OpenAPI + both frontends
./build.sh --skip-openapi   # Skip OpenAPI generation
cd frontend
npm run lint                # Fix linting errors first
npm run build              # 5-15 seconds if successful (builds server frontend)

# Build Python wheel with both frontends
./build.sh --with-wheel     # Generates OpenAPI clients, builds frontends, and packages

# Backend testing (when dependencies installed)
mycelium-ai server &       # Start server for testing
curl http://localhost:8000/api/library/stats  # Test API
curl http://localhost:8000/openapi.yaml       # Verify OpenAPI spec served

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

### OpenAPI-First Design
The project uses an **API-first approach** with OpenAPI specifications as the source of truth:
- **Server API**: Defined in `openapi/server_openapi.yaml` (port 8000)
- **Worker API**: Defined in `openapi/worker_openapi.yaml` (port 3001 by default)
- **Client Generation**: TypeScript and Python clients generated from specs via `openapi/generate.sh`
- **Validation**: FastAPI apps load external specs to ensure API compliance

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

# OpenAPI Documentation
GET  /openapi.yaml                  # Download OpenAPI spec
GET  /docs                          # Swagger UI (if not using external spec)
```

### Worker API Endpoints (Port 3001 by default, configurable)
```bash
# Worker Configuration (client-side API)
GET  /api/config                    # Get current worker config
POST /api/config                    # Update worker configuration (hot-reload)

# OpenAPI Documentation
GET  /openapi.yaml                  # Download OpenAPI spec
```

**Note**: The worker API port is configurable via `client_api.port` in `client_config.yml`. Default is 3001, though the OpenAPI spec example shows 8001.

### Using Generated Clients
```typescript
// Frontend: Use generated TypeScript clients
import { api } from '@/server_api/client';  // Server API client
import { workerApi } from '@/worker_api/client';  // Worker API client

// Example: Search for tracks
const results = await api.searchText({ q: 'jazz piano' });

// Example: Get worker configuration
const config = await workerApi.getWorkerConfig();
```

```python
# Backend: Use generated Pydantic models for validation
from mycelium.api.generated_sources.server_schemas.models import (
    SearchResultResponse,
    LibraryStatsResponse,
)
from mycelium.api.generated_sources.worker_schemas.models import (
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
- **Generated code import errors**: Run `bash openapi/generate.sh` to regenerate clients
- **Type mismatch in frontend**: Regenerate TypeScript clients from updated OpenAPI spec
- **Pydantic validation errors**: Check that OpenAPI spec matches FastAPI endpoint implementation

### OpenAPI-Related Issues
- **"Module 'generated_sources' not found"**: Run `bash openapi/generate.sh` first
- **TypeScript errors in generated code**: OpenAPI spec may have invalid types, check the YAML
- **Pydantic v1 vs v2 errors**: Generated code is auto-converted by `fix_pydantic_v2.py`
- **API response doesn't match spec**: Update OpenAPI spec first, then regenerate clients
- **Frontend can't import from '@/server_api/client'**: Check that `frontend/src/server_api/generated/` exists

### Build and Deployment Issues
- **Frontend build succeeds but missing in wheel**: Run `./build.sh --with-wheel` not just `python -m build`
- **Server mode shows 404 for frontend**: Check that `backend/mycelium/frontend_dist/` exists after build
- **Client mode shows 404 for frontend**: Check that `backend/mycelium/client_frontend_dist/` exists after build
- **API endpoints return 404**: Verify FastAPI app is loading the correct OpenAPI spec
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

# OpenAPI + Frontend build workflow
bash openapi/generate.sh    # Generate clients from OpenAPI specs
./build.sh                  # Build both frontends (includes OpenAPI generation)
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
bash openapi/generate.sh            # Regenerate API clients
mycelium-ai server                  # Start server and test web interface
curl http://localhost:8000/api/library/stats  # Test API
curl http://localhost:8000/openapi.yaml       # Verify OpenAPI spec
```
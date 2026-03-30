# Mycelium Development Instructions

**ALWAYS follow these instructions first. Only use additional search or commands if the information here is incomplete.**

Mycelium is a music recommendation system with AI-powered embeddings for Plex media servers. Python backend (FastAPI), Next.js frontend, three embedding models (CLAP, MuQ, MuQ-MuLan), ChromaDB vector database.

## Architecture

Hexagonal / clean architecture with four layers:

- **Domain** (`backend/mycelium/domain/`): Models, repository interfaces (ABCs), no external deps
- **Application** (`backend/mycelium/application/`): Use cases, services, model registry, job queue
- **Infrastructure** (`backend/mycelium/infrastructure/`): Plex adapter, ChromaDB, SQLite, embedding models
- **API** (`backend/mycelium/api/`): FastAPI endpoints, Pydantic v2 DTOs

### Key Patterns
- **Dependency injection** via constructor parameters
- **Repository pattern** for data access (domain interfaces, infrastructure implementations)
- **Model registry** (`application/embedding/registry.py`): Add new model = 1 adapter file + 1 registry entry
- **Hand-written API types** (no code generation): `api/schemas.py` (Python) <-> `server_api/types.ts` (TypeScript)

### Dual Frontend Builds
Same codebase, two builds with different `API_BASE_URL`:
- **Server frontend** (`/api` relative) -> `backend/mycelium/frontend_dist/` (port 8000, full UI)
- **Worker frontend** (`http://localhost:3001/api` absolute) -> `backend/mycelium/client_frontend_dist/` (port 3001, config only)

### Two YAML Configurations
- **Server**: `~/.config/mycelium/config.yml` (`MyceliumConfig` in `config.py`), hot-reloadable
- **Worker**: `~/.config/mycelium/client_config.yml` (`MyceliumClientConfig` in `client_config.py`), hot-reloadable
- Both auto-generated on first run. No environment variable support.

## Code Standards

### Python
- Type hints on all functions (Python 3.9+ syntax)
- Google-style docstrings
- Structured logging (`logger = logging.getLogger(__name__)`), never `print()`
- Specific exception types, no bare `except:`
- Imports grouped: stdlib, third-party, local (isort)
- Line length: 88 chars (Black)
- `@dataclass` for data containers

### TypeScript / React
- Strict TypeScript, no `any` without justification
- Explicit interfaces for component props
- Loading/error states for all API calls
- Hooks patterns, no class components
- Import from `@/server_api/client` or `@/worker_api/client`

### Git
- Branches: `feature/description` or `fix/description`
- Commits: `type(scope): description` (conventional commits)

## API Workflow

When changing the API:
1. Edit Python DTOs in `backend/mycelium/api/schemas.py`
2. Edit TypeScript types in `frontend/src/server_api/types.ts` (or `worker_api/types.ts`)
3. Update FastAPI endpoints in `app.py` or `client_app.py`
4. Update frontend client methods if new endpoints added

Keep `schemas.py` and `types.ts` in sync at all times.

## Project Structure

```
backend/mycelium/
  domain/
    models.py              # Track, SearchResult, MediaServerType
    repositories.py        # EmbeddingGenerator, TrackRepository, etc. (ABCs)
    worker.py              # Worker, Task domain models
  application/
    services.py            # MyceliumService (main orchestrator)
    search/use_cases.py    # Text/audio/similar search
    library/use_cases.py   # Scan, process, progress
    embedding/registry.py  # MODEL_REGISTRY (add models here)
    embedding/factory.py   # Creates generators from config
    jobs/queue.py          # Worker task queue
    error_log.py           # In-memory structured error log
  infrastructure/
    plex/adapter.py        # Plex media server adapter
    model/base.py          # BaseAudioEmbeddingGenerator (shared logic)
    model/clap.py          # CLAP adapter (text + audio)
    model/muq.py           # MuQ adapter (audio only)
    model/muq_mulan.py     # MuQ-MuLan adapter (text + audio)
    db/chroma.py           # ChromaDB vector store
    db/tracks.py           # SQLite track metadata
  api/
    app.py                 # Server API endpoints + composition root
    client_app.py          # Worker config API
    schemas.py             # Hand-written Pydantic v2 DTOs
    worker_models.py       # Internal worker protocol models
  config.py                # Server YAML config (MyceliumConfig)
  client_config.py         # Worker YAML config (MyceliumClientConfig)
  client.py                # GPU worker implementation
  main.py                  # CLI entry point (Typer)

frontend/src/
  server_api/types.ts      # TypeScript types (mirrors schemas.py)
  server_api/client.ts     # Typed fetch wrapper for server API
  worker_api/types.ts      # Worker API types
  worker_api/client.ts     # Typed fetch wrapper for worker API
  components/              # React components (Next.js App Router)
```

## Embedding Models

Three registered models in `MODEL_REGISTRY`:

| Key | Adapter | Text Search | Notes |
|-----|---------|-------------|-------|
| `clap` | `clap.py` -> `CLAPEmbeddingGenerator` | Yes | CLAP (HTSAT + RoBERTa), sr=48000, legacy |
| `muq` | `muq.py` -> `MuQEmbeddingGenerator` | No | MuQ (Mel-RVQ SSL), sr=24000, best acoustic quality |
| `muq_mulan` | `muq_mulan.py` -> `MuQMuLanEmbeddingGenerator` | Yes | MuQ + MuLan text tower, sr=24000 |

All inherit from `BaseAudioEmbeddingGenerator` in `base.py` which handles:
- Chunking (non-overlapping windows), micro-batching, L2 normalization
- Dtype selection (bfloat16 > float16 > float32) with smoke test fallback
- `_fp16_blacklisted = True` for MuQ/MuQ-MuLan (nnAudio incompatibility)
- Per-file error tracking via `last_batch_errors`

Config dataclasses: `CLAPConfig`, `MuQConfig`, `MuQMuLanConfig` in `config.py`.

## Build & Dev Commands

```bash
# Setup
pip install -e .                    # Backend (slow: torch ~2GB)
cd frontend && npm install          # Frontend

# Development
mycelium-ai server                  # Server + UI at http://localhost:8000
mycelium-ai client                  # Worker + config UI at http://localhost:3001

# Build
./build.sh                          # Both frontends
./build.sh --with-wheel             # Frontends + Python wheel

# Validation
cd frontend && npm run lint && npm run build
```

## Key API Endpoints

Server (port 8000):

| Endpoint | Purpose |
|----------|---------|
| `POST /api/library/scan` | Scan Plex library |
| `POST /api/library/process` | Process embeddings (workers or server) |
| `POST /api/library/process/stop` | Stop processing |
| `GET /api/library/stats` | Database statistics |
| `GET /api/library/tracks` | Paginated tracks (filters: artist, album, title) |
| `GET /api/search/text?q=...` | Text search |
| `POST /api/search/audio` | Audio file search |
| `GET /api/similar/by_track/{id}` | Similar tracks |
| `GET/POST /api/config` | Read/write config (hot-reload) |
| `GET /api/capabilities` | Model capabilities |
| `GET /api/queue/overview` | Queue dashboard |
| `GET /api/errors` | Structured error log |
| `POST /api/playlists/create` | Create Plex playlist |
| `GET /docs` | Swagger UI |

Worker (port 3001): `GET/POST /api/config`, `GET /api/status`, `POST /api/stop`
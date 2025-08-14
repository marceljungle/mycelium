# Mycelium Development Instructions

**ALWAYS follow these instructions first. Only use additional search or commands if the information here is incomplete or found to be in error.**

Mycelium is a Python-based music recommendation system with AI-powered embeddings that connects to Plex media servers. It features a Python backend with FastAPI, a Next.js frontend, and uses CLAP (Contrastive Language-Audio Pre-training) for semantic music search.

## Working Effectively

### Bootstrap and Setup
**CRITICAL: Set long timeouts for all installation commands. NEVER CANCEL long-running installs.**

1. **Install Python backend dependencies:**
   ```bash
   pip install -e .
   ```
   - **NEVER CANCEL:** This takes 15-45 minutes due to ML dependencies (torch, transformers, librosa)
   - **TIMEOUT: Use 60+ minutes minimum**
   - If network timeouts occur: `pip install --timeout 600 --retries 5 -e .`
   - Known issue: May fail due to PyPI network connectivity in CI environments

2. **Install frontend dependencies:**
   ```bash
   cd frontend
   npm install
   ```
   - **TIMING: 1.5 minutes (90 seconds measured)**  
   - **TIMEOUT: Use 3+ minutes minimum**
   - **NEVER CANCEL:** Wait for completion even if it appears slow

3. **Setup configuration (YAML recommended):**
   ```bash
   # Preferred: YAML configuration
   mkdir -p ~/.config/mycelium
   cp config.example.yml ~/.config/mycelium/config.yml
   # Edit ~/.config/mycelium/config.yml and add your Plex token
   
   # Alternative: Environment variables (legacy)
   cp .env.example .env
   # Edit .env and add your Plex token
   ```
   - **YAML config**: `~/.config/mycelium/config.yml` (preferred method)
   - **Environment variables**: Still supported for backward compatibility
   - **Priority**: Environment variables > YAML config > defaults

### Build and Test
1. **Build frontend:**
   ```bash
   cd frontend
   npm run build
   ```
   - **TIMING: 5-15 seconds for successful builds**
   - **TIMEOUT: Use 5+ minutes minimum**
   - May fail due to Google Fonts network access in restricted environments
   - ESLint errors will block builds - run `npm run lint` to identify issues

2. **Run development servers:**
   ```bash
   # Backend API (requires dependencies installed)
   mycelium api --host localhost --port 8000
   
   # Frontend dev server (in separate terminal)
   cd frontend
   npm run dev
   ```
   - **Frontend timing: Starts in 2-3 seconds**
   - **Frontend URL: http://localhost:3000**
   - **API URL: http://localhost:8000**

### CLI Commands
**All CLI commands require Python dependencies installed successfully:**

```bash
# NEW SEPARATED WORKFLOW (Recommended):
# 1. Scan Plex library (save metadata to database)
mycelium scan

# 2. Process embeddings (from database, resumable)
mycelium process
# **NEVER CANCEL:** Takes 30+ minutes for large libraries

# LEGACY WORKFLOW (Still supported):
# Process entire library (scan + generate embeddings + index)
mycelium process  # Uses new separated workflow internally

# Start GPU worker for distributed processing (on powerful machines)
mycelium client --server-host your-server-ip
# **RECOMMENDED:** Run on machines with GPUs for fast CLAP processing

# Search by text
mycelium search-text "upbeat 80s synthpop"

# Search by audio file  
mycelium search-audio /path/to/audio.mp3

# Show database statistics
mycelium stats

# Start API server only
mycelium api

# Start server mode (API + Frontend)
mycelium server
```

### Distributed Worker Architecture
**NEW: Worker-First Processing Design**

Mycelium now prioritizes distributed GPU workers over server processing:

1. **Optimal Setup:** Run server on lightweight hardware (Orange Pi, etc.) + GPU workers on powerful machines
2. **Processing Flow:** 
   - Frontend → Server checks for active workers
   - If workers available: Creates distributed tasks
   - If no workers: Asks user confirmation for server processing
3. **Worker Commands:**
   ```bash
   # On powerful GPU machine
   mycelium client --server-host 192.168.1.100
   
   # Server will automatically detect and use workers
   # Frontend "Process Embeddings" uses workers when available
   ```

### API Endpoints
**New Separated Workflow Endpoints:**

```bash
# Library Operations
POST /api/library/scan              # Scan Plex library, save metadata to database
POST /api/library/process           # Process embeddings from database (resumable)
POST /api/library/process/server    # Force processing on server (with confirmation)
POST /api/library/process/stop      # Stop current processing operation
GET /api/library/progress           # Get processing progress and statistics
GET /api/library/can_resume         # Check if processing can be resumed
GET /api/library/stats              # Get database and library statistics

# Legacy Endpoints (still supported)
POST /api/library/process/legacy    # Old workflow (scan + process combined)

# Worker Coordination  
POST /workers/register              # Register a worker with the server
GET /workers/get_job                # Get next job for a worker
POST /workers/submit_result         # Submit completed job result
GET /api/queue/stats                # Get job queue statistics
```

## Validation Scenarios

### Manual Testing Requirements
**ALWAYS test these scenarios after making changes:**

1. **Frontend Interface Test:**
   - Start frontend dev server: `cd frontend && npm run dev`
   - Open http://localhost:3000
   - Verify the Mycelium interface loads with:
     - 🍄 Mycelium branding and navigation
     - Search input field with example buttons
     - Library Statistics panel
     - Three feature cards at bottom (Semantic Search, AI-Powered, Plex Integration)

2. **Backend API Test (when dependencies work):**
   - Start API: `mycelium api`
   - Test endpoints: 
     - `curl http://localhost:8000/api/library/stats` - Database statistics
     - `curl -X POST http://localhost:8000/api/library/scan` - Scan library
     - `curl http://localhost:8000/api/library/progress` - Processing progress
   - Should return database statistics or connection error

3. **Full Integration Test (requires Plex setup):**
   - Configure YAML config with valid Plex token or set PLEX_TOKEN environment variable
   - Run: `mycelium scan` to test Plex connectivity and database scanning
   - Run: `mycelium stats` to verify database and track information
   - Optional: Run `mycelium process` to test embedding processing (resumable)

4. **Separated Workflow Test (new feature):**
   - Start server: `mycelium api`
   - Test scanning: `curl -X POST http://localhost:8000/api/library/scan`
   - Test progress: `curl http://localhost:8000/api/library/progress`
   - Test processing: `curl -X POST http://localhost:8000/api/library/process`
   - Test stopping: `curl -X POST http://localhost:8000/api/library/process/stop`
   - Frontend: Use "Scan Library" and "Process Embeddings" buttons separately

5. **Worker Integration Test (for distributed processing):**
   - Start server: `mycelium api`
   - Start worker (separate machine): `mycelium client --server-host your-server-ip`
   - In frontend: Click "Process Embeddings" - should show worker processing
   - Without workers: Should show confirmation dialog for server processing

### Known Network Issues
- **PyPI timeouts:** Python dependency installation may fail in CI/restricted networks
- **Google Fonts errors:** Frontend build may fail due to fonts.googleapis.com access
- **Workaround:** These are infrastructure issues, not code problems

## Code Quality and CI

### Linting and Formatting
```bash
# Python (when dependencies installed)
black src/
isort src/
mypy src/

# Frontend
cd frontend
npm run lint
npm run build  # Must pass for deployment
```

### Pre-commit Requirements
- **ALWAYS run `npm run lint` for frontend changes** 
- Python linting requires dependencies installed
- Frontend build must succeed without errors

## Project Structure and Navigation

### Key Directories
```
mycelium/
├── src/mycelium/           # Python backend
│   ├── domain/             # Core business logic and models
│   ├── application/        # Use cases and services (MyceliumService)
│   │   ├── job_queue.py    # Worker coordination and task distribution
│   │   └── workflow_use_cases.py  # NEW: Separated workflow use cases
│   ├── infrastructure/     # External adapters (Plex, CLAP, ChromaDB)
│   │   └── track_database.py  # NEW: Track metadata database
│   ├── api/                # FastAPI web API endpoints
│   ├── client.py           # GPU worker client for distributed processing
│   ├── main.py             # CLI entry point with Typer
│   ├── config.py           # Configuration management
│   └── config_yaml.py      # NEW: YAML configuration manager
├── frontend/               # Next.js frontend  
│   ├── src/app/            # Next.js app router pages
│   ├── src/components/     # React components
│   └── package.json        # Frontend dependencies
├── .env.example            # Environment configuration template (legacy)
├── config.example.yml      # NEW: YAML configuration template (preferred)
├── pyproject.toml          # Python project configuration
└── requirements.txt        # Python dependencies
```

### Important Files to Check
- **Always check `src/mycelium/config.py` and `src/mycelium/config_yaml.py`** after configuration changes
- **Check `frontend/src/components/LibraryStats.tsx`** for API integration and separated workflow UI
- **Check `src/mycelium/api/app.py`** for new API endpoints (`/scan`, `/process`, `/progress`)
- **Check `src/mycelium/main.py`** for CLI command modifications
- **Check `src/mycelium/application/job_queue.py`** for worker coordination
- **Check `src/mycelium/client.py`** for GPU worker functionality
- **Check `src/mycelium/application/workflow_use_cases.py`** for separated workflow logic
- **Check `src/mycelium/infrastructure/track_database.py`** for track database operations

## Dependencies and Requirements

### System Requirements
- **Python 3.9+ (tested with Python 3.12)**
- **Node.js 18+ (tested with Node.js 20.19)**
- **Plex Media Server with music library**
- **GPU recommended for faster CLAP embeddings**

### Major Python Dependencies (Heavy Downloads)
- `torch>=2.0.0` - Deep learning framework (~2GB download)
- `transformers>=4.30.0` - Hugging Face transformers (~500MB)
- `librosa>=0.10.0` - Audio analysis library
- `chromadb>=0.4.0` - Vector database
- `plexapi>=4.15.0` - Plex server integration

### Frontend Dependencies  
- `next@15.4.5` - React framework
- `react@19.1.0` - UI library
- `typescript@^5` - Type checking
- `tailwindcss@^4` - CSS framework

## Common Issues and Solutions

### "Module not found" errors
- Ensure Python dependencies installed: `pip install -e .`
- Use `PYTHONPATH=/path/to/mycelium/src python -m mycelium.main` if needed

### Frontend build failures
- Check for ESLint errors: `npm run lint`
- Verify all imports are correct
- Check network access for Google Fonts

### Plex connection issues  
- Verify PLEX_TOKEN in YAML config file or environment variable
- Check PLEX_URL points to correct server
- Test with: `mycelium scan` (now saves to database for resumable processing)

### Configuration migration
- **New users**: Use YAML config at `~/.config/mycelium/config.yml` (preferred)
- **Existing users**: Environment variables still work for backward compatibility
- **Migration**: Copy settings from `.env` to `~/.config/mycelium/config.yml`
- **Priority**: Environment variables override YAML settings

### Performance Notes
- **First-time model downloads:** CLAP models (~1GB) download on first use
- **Embedding generation:** GPU-accelerated on workers, CPU-intensive on server
- **Distributed processing:** Workers keep models loaded for efficiency
- **Database indexing:** ChromaDB operations scale with library size
- **Worker optimization:** Models loaded once per worker session, not per track
- **Separated workflow:** Scanning and processing can be done independently and resumed
- **Database storage:** Track metadata stored in SQLite for faster resumable operations

## Quick Reference Commands

```bash
# Complete setup from scratch
pip install -e .                    # 15-45 min, NEVER CANCEL
cd frontend && npm install          # 1.5 min

# Configuration (choose one method)
# PREFERRED: YAML configuration
mkdir -p ~/.config/mycelium && cp config.example.yml ~/.config/mycelium/config.yml
# LEGACY: Environment variables  
cp .env.example .env               # Edit with Plex details

# Development workflow  
cd frontend && npm run dev          # Start frontend
mycelium api                       # Start backend (separate terminal)

# NEW SEPARATED WORKFLOW (recommended):
mycelium scan                      # Scan Plex library to database
mycelium process                   # Process embeddings (resumable, 30+ min, NEVER CANCEL)
mycelium search-text "jazz piano"  # Test search

# Alternative: Legacy single command
mycelium process                   # Still works, uses separated workflow internally

# Distributed processing (recommended)
mycelium client --server-host 192.168.1.100  # Start GPU worker

# Validation
npm run lint                       # Frontend linting
npm run build                      # Frontend build test
mycelium stats                     # Backend health check
```
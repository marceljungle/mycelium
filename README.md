# Mycelium

Plex music collection creator and recommendation system using LAION-CLAP embeddings.

![Mycelium Frontend](https://github.com/user-attachments/assets/1a838b24-6f74-43ea-bf85-31f66efaffdb)

## Overview

Mycelium is a modern application that connects to your Plex media server, extracts music tracks, generates AI embeddings using the CLAP (Contrastive Language-Audio Pre-training) model, and provides intelligent music recommendations based on semantic similarity.

## Features

### 🎵 Search & Discovery
- **Text-to-Music Search**: Find music tracks using natural language descriptions
- **Audio-to-Music Search**: Upload audio files to find similar tracks in your library
- **Library Search**: Browse and search your Plex tracks for recommendations
- **Semantic Similarity**: AI-powered recommendations based on sound, mood, and style

### 🏗️ Architecture & Integration
- **Plex Integration**: Seamlessly connects to your Plex media server
- **AI-Powered Embeddings**: Uses LAION's CLAP model for semantic audio understanding
- **Vector Database**: ChromaDB for efficient similarity search
- **Separated Workflows**: Independent scanning and processing operations
- **Resumable Processing**: Stop and resume embedding generation anytime

### 🌐 User Interface
- **Modern Frontend**: Next.js + TypeScript + Tailwind CSS web interface
- **Three-Section Navigation**: Search, Library, and Settings pages
- **Audio File Upload**: Drag-and-drop interface for audio similarity search
- **Settings Management**: Complete configuration interface
- **Real-time Progress**: Live updates during library processing

### ⚙️ Configuration & Deployment
- **YAML Configuration**: Clean, hierarchical configuration system
- **Platform-Specific Paths**: User data directories (Windows/macOS/Linux)
- **Environment Override**: Environment variables can override YAML settings
- **Distributed Processing**: GPU workers for faster embedding generation
- **Proper Logging**: Structured logging with configurable levels

## Installation

### Prerequisites

- Python 3.9 or higher
- Node.js 18 or higher
- Plex Media Server with a music library
- GPU recommended (but not required) for faster embedding generation

### Backend Setup

1. Clone the repository:
```bash
git clone https://github.com/marceljungle/mycelium.git
cd mycelium
```

2. Install the Python package:
```bash
pip install -e .
```

3. Set up configuration:
```bash
# Copy example configuration
mkdir -p ~/.config/mycelium
cp config.example.yml ~/.config/mycelium/config.yml

# Edit configuration file with your settings
# Add your Plex token and adjust paths as needed
```

### Frontend Setup

1. Install frontend dependencies:
```bash
cd frontend
npm install
```

2. Start the frontend development server:
```bash
npm run dev
```

## Configuration

Mycelium uses a YAML-based configuration system with automatic platform-specific data directories.

### Configuration File Location

- **Linux/Unix**: `~/.config/mycelium/config.yml`
- **macOS**: `~/.config/mycelium/config.yml`
- **Windows**: `%APPDATA%\mycelium\config.yml`

### Data Storage Locations

- **Linux/Unix**: `~/.local/share/mycelium/`
- **macOS**: `~/Library/Application Support/mycelium/`
- **Windows**: `%LOCALAPPDATA%\mycelium\`

### Example Configuration

```yaml
# Plex server configuration
plex:
  url: http://localhost:32400
  token: your_plex_token_here
  music_library_name: Music

# API server configuration
api:
  host: 0.0.0.0  # Default changed to accept external connections
  port: 8000
  reload: false

# Client configuration for worker connections
client:
  server_host: localhost
  server_port: 8000
  model_id: laion/clap-htsat-unfused

# Logging configuration
logging:
  level: INFO
  format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  file: null  # Auto-determined based on platform
```

### Environment Variable Override

You can still use environment variables to override any configuration setting:

```bash
export PLEX_TOKEN="your_token_here"
export API_HOST="0.0.0.0"
export LOG_LEVEL="DEBUG"
```

## Usage

### Command Line Interface

All commands now use configuration defaults. Host and port parameters are optional:

1. **Start the full server** (API + Frontend):
```bash
mycelium server
# Optionally override config: mycelium server --host 127.0.0.1 --port 3000
```

2. **Start API server only**:
```bash
mycelium api
```

3. **Start GPU worker client**:
```bash
mycelium client
# Optionally specify server: mycelium client --server-host 192.168.1.100
```

4. **Scan your Plex library**:
```bash
mycelium scan
```

5. **Process embeddings** (resumable):
```bash
mycelium process
```

6. **Search by text description**:
```bash
mycelium search-text "upbeat 80s synthpop with female vocals"
```

7. **Search by audio file**:
```bash
mycelium search-audio /path/to/audio/file.mp3
```

8. **View database statistics**:
```bash
mycelium stats
```

### Web Interface

After starting the server, visit `http://localhost:3000` to access the web interface:

#### 🔍 Search Section
- **Text Search**: Enter natural language descriptions like "melancholic indie rock" or "upbeat electronic dance music"
- **Audio Search**: Upload audio files (MP3, WAV, FLAC, OGG) to find similar tracks in your library
- **Quick Suggestions**: Pre-filled example queries to get started

#### 📚 Library Section  
- **Track Browser**: Search and browse your scanned Plex music library
- **Track-based Recommendations**: Select any track to get AI-powered recommendations
- **Real-time Search**: Filter tracks by artist, album, or title

#### ⚙️ Settings Section
- **Plex Configuration**: Set up your Plex server URL, token, and library name
- **API Settings**: Configure server host, port, and auto-reload options
- **Client Settings**: Set default server connection for GPU workers
- **AI Model Settings**: Configure CLAP model parameters and processing options
- **Database Settings**: Adjust ChromaDB and batch processing settings
- **Logging Configuration**: Set log levels and output options

### Distributed Processing

For large libraries, use distributed GPU workers for faster processing:

1. **On a powerful machine with GPU**:
```bash
mycelium client --server-host your-server-ip
```

2. **On the main server**:
```bash
mycelium server
```

The system automatically detects available workers and distributes embedding generation tasks.

## API Endpoints

### Library Management
- `POST /api/library/scan` - Scan Plex library and save metadata to database
- `POST /api/library/process` - Process embeddings from database (resumable)
- `POST /api/library/process/stop` - Stop current processing operation
- `GET /api/library/progress` - Get processing progress and statistics
- `GET /api/library/stats` - Get database and library statistics

### Search
- `GET /api/search/text?q={query}&n_results={count}` - Text-based search
- `POST /api/search/audio` - Audio file similarity search (multipart/form-data)

### Workers
- `POST /workers/register` - Register a worker with the server
- `GET /workers/get_job` - Get next job for a worker
- `POST /workers/submit_result` - Submit completed job result

## Architecture

The project follows clean architecture principles with modern development practices:

### Backend Architecture
- **Domain Layer**: Core business models and interfaces  
- **Application Layer**: Use cases and business logic orchestration
- **Infrastructure Layer**: External service adapters (Plex, CLAP, ChromaDB)
- **API Layer**: FastAPI web interface with separated workflows

### Frontend Architecture  
- **Next.js 15**: React framework with app router
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first styling
- **Component-based**: Reusable UI components with proper state management

### Data Flow
1. **Library Scanning**: Plex API → SQLite database (metadata storage)
2. **Embedding Processing**: Database → CLAP model → ChromaDB (vector storage)
3. **Search Operations**: User input → ChromaDB similarity search → Results
4. **Worker Distribution**: Job queue → GPU workers → Result aggregation

### Database Strategy
- **SQLite**: Track metadata, processing state, and session tracking
- **ChromaDB**: Vector embeddings for similarity search
- **Platform-specific storage**: User data directories for cross-platform compatibility

## Python API

You can also use Mycelium programmatically:

```python
from mycelium.config_yaml import MyceliumConfig
from mycelium.application.services import MyceliumService

# Load configuration
config = MyceliumConfig.load_from_yaml()
config.setup_logging()

# Initialize the service
service = MyceliumService(
    plex_url=config.plex.url,
    plex_token=config.plex.token,
    music_library_name=config.plex.music_library_name,
    db_path=config.chroma.get_db_path(),
    collection_name=config.chroma.collection_name,
    model_id=config.clap.model_id
)

# Scan library and process embeddings
scan_result = service.scan_library_to_database()
process_result = service.process_embeddings_from_database()

# Search for music
results = service.search_similar_by_text("melancholic indie rock")
for result in results:
    print(f"{result.track.artist} - {result.track.title} (similarity: {result.similarity_score:.3f})")
```

## Development

### Development Installation

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Install frontend development dependencies
cd frontend && npm install
```

### Code Quality

```bash
# Python formatting and linting
black src/
isort src/
mypy src/

# Frontend linting and building
cd frontend
npm run lint
npm run build
```

### Running Tests

```bash
# Python tests (when available)
pytest

# Configuration system test
python test_config.py
```

## Project Structure

```
mycelium/
├── src/mycelium/              # Python backend
│   ├── domain/                # Core business logic and models
│   ├── application/           # Use cases and services
│   │   ├── services.py        # Main MyceliumService orchestrator
│   │   ├── job_queue.py       # Worker coordination and task distribution
│   │   └── workflow_use_cases.py  # Separated workflow use cases
│   ├── infrastructure/        # External adapters
│   │   ├── plex_adapter.py    # Plex Media Server integration
│   │   ├── clap_adapter.py    # CLAP model integration
│   │   ├── chroma_adapter.py  # ChromaDB vector database
│   │   └── track_database.py  # SQLite track metadata database
│   ├── api/                   # FastAPI web API
│   │   └── app.py             # API endpoints and routes
│   ├── config_yaml.py         # YAML configuration management
│   ├── main.py                # CLI entry point with Typer
│   └── client.py              # GPU worker client for distributed processing
├── frontend/                  # Next.js frontend
│   ├── src/
│   │   ├── app/               # Next.js app router pages
│   │   └── components/        # React components
│   │       ├── Navigation.tsx      # Three-section navigation system
│   │       ├── SearchInterface.tsx # Text + audio search interface
│   │       ├── LibraryPage.tsx     # Library browsing and recommendations
│   │       ├── SettingsPage.tsx    # Configuration management UI
│   │       └── LibraryStats.tsx    # Statistics and library operations
│   └── package.json
├── config.example.yml         # YAML configuration template
├── .env.example              # Environment variables (legacy support)
├── pyproject.toml            # Python project configuration
├── requirements.txt          # Python dependencies
└── README.md
```

## Configuration Locations

### User Data Directories (Platform-specific)

**Linux/Unix:**
- Config: `~/.config/mycelium/config.yml`
- Data: `~/.local/share/mycelium/`
- Logs: `~/.local/share/mycelium/mycelium.log`

**macOS:**
- Config: `~/.config/mycelium/config.yml`
- Data: `~/Library/Application Support/mycelium/`
- Logs: `~/Library/Logs/mycelium/mycelium.log`

**Windows:**
- Config: `%APPDATA%\mycelium\config.yml`
- Data: `%LOCALAPPDATA%\mycelium\`
- Logs: `%LOCALAPPDATA%\mycelium\mycelium.log`

## Troubleshooting

### Common Issues

1. **"Unable to connect to API"**: Ensure the API server is running with `mycelium api` or `mycelium server`

2. **"No tracks scanned yet"**: Run `mycelium scan` to scan your Plex library first

3. **Missing Plex token**: Get your token from [Plex support documentation](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)

4. **Database paths**: Use the Settings page to configure custom database locations if needed

5. **GPU worker connection**: Ensure firewall allows connections on the configured port (default: 8000)

### Performance Tips

- Use GPU workers for faster embedding processing on large libraries
- Configure appropriate batch sizes based on available memory
- Use the separated workflow to pause/resume processing as needed
- Monitor processing progress through the web interface or API endpoints

## Contributing

Contributions are welcome! Please ensure your changes:

1. Follow the existing code style and architecture patterns
2. Include proper TypeScript types for frontend components
3. Use the logging system instead of print statements
4. Test both CLI and web interface functionality
5. Update documentation for new features

## License

MIT License - see LICENSE file for details.

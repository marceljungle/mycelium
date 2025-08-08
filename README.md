# Mycelium

Plex music collection creator and recommendation system using LAION-CLAP embeddings.

![Mycelium Frontend](https://github.com/user-attachments/assets/1a838b24-6f74-43ea-bf85-31f66efaffdb)

## Overview

Mycelium is a modern application that connects to your Plex media server, extracts music tracks, generates AI embeddings using the CLAP (Contrastive Language-Audio Pre-training) model, and provides intelligent music recommendations based on semantic similarity.

## Features

- **Plex Integration**: Seamlessly connects to your Plex media server to access your music library
- **AI-Powered Embeddings**: Uses LAION's CLAP model to generate semantic embeddings for audio tracks
- **Vector Database**: Stores embeddings in ChromaDB for efficient similarity search
- **Text-to-Music Search**: Find music tracks using natural language descriptions
- **Audio-to-Music Search**: Find similar tracks based on audio file input
- **REST API**: FastAPI-based web API for frontend integration
- **Modern Frontend**: Next.js + TypeScript + Tailwind CSS web interface
- **Clean Architecture**: Domain-driven design with proper separation of concerns

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

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your Plex token
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

## Usage

### Command Line Interface

1. **Scan your Plex library**:
```bash
mycelium scan
```

2. **Process the entire library** (scan + generate embeddings + index):
```bash
mycelium process
```

3. **Search by text description**:
```bash
mycelium search-text "upbeat 80s synthpop with female vocals"
```

4. **Search by audio file**:
```bash
mycelium search-audio /path/to/audio/file.mp3
```

5. **Show database statistics**:
```bash
mycelium stats
```

6. **Start the API server**:
```bash
mycelium api
```

### Web Interface

1. Start the API server:
```bash
mycelium api
```

2. Start the frontend (in another terminal):
```bash
cd frontend
npm run dev
```

3. Open http://localhost:3000 in your browser

### Python API

```python
from mycelium import MyceliumService

# Initialize the service
service = MyceliumService(
    plex_url="http://your-plex-server:32400",
    plex_token="your-plex-token"
)

# Scan library and process embeddings
service.full_library_processing()

# Search for music
results = service.search_similar_by_text("melancholic indie rock")
for result in results:
    print(f"{result.track.artist} - {result.track.title} (similarity: {result.similarity_score:.3f})")
```

### REST API

Start the API server:
```bash
mycelium api
```

Then use the endpoints:
- `GET /api/library/stats` - Get database statistics
- `GET /api/search/text?q=your+query` - Search by text
- `POST /api/library/process` - Process the entire library

## Architecture

The project follows clean architecture principles:

- **Domain Layer**: Core business models and interfaces
- **Application Layer**: Use cases and business logic orchestration  
- **Infrastructure Layer**: External service adapters (Plex, CLAP, ChromaDB)
- **API Layer**: FastAPI web interface
- **Frontend**: Next.js + TypeScript + Tailwind CSS

## Configuration

Configuration is handled through environment variables (see `.env.example`):

- `PLEX_URL`: Plex server URL (default: "http://localhost:32400")
- `PLEX_TOKEN`: Plex authentication token (required)
- `PLEX_MUSIC_LIBRARY`: Name of music library (default: "Music")
- `API_HOST`: API server host (default: "localhost")
- `API_PORT`: API server port (default: 8000)

## Development

### Development Installation

```bash
pip install -e ".[dev]"
```

### Code Formatting

```bash
black src/
isort src/
```

### Type Checking

```bash
mypy src/
```

### Running Tests

```bash
pytest
```

## Project Structure

```
mycelium/
├── src/mycelium/           # Python backend
│   ├── domain/             # Core business logic
│   ├── application/        # Use cases and services
│   ├── infrastructure/     # External adapters
│   ├── api/                # FastAPI web API
│   └── main.py             # CLI entry point
├── frontend/               # Next.js frontend
│   ├── src/
│   │   ├── app/            # Next.js app router
│   │   └── components/     # React components
│   └── package.json
├── old_code/               # Original code (moved)
├── pyproject.toml          # Python project config
├── requirements.txt        # Python dependencies
└── README.md
```

## License

MIT License - see LICENSE file for details.

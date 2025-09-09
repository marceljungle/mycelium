# 🍄 Mycelium

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-15.4.5-black)](https://nextjs.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-red)](https://pytorch.org/)

AI-powered music recommendation system for Plex using semantic search with CLAP embeddings.

![Mycelium Frontend](https://github.com/user-attachments/assets/1a838b24-6f74-43ea-bf85-31f66efaffdb)

## What is this?

Mycelium connects to your Plex media server and uses AI to understand your music collection. Search for songs using natural language ("melancholic indie rock") or upload audio files to find similar tracks. Uses CLAP (Contrastive Language-Audio Pre-training) for semantic music understanding.

## How it works

1. **Scan** - Connects to Plex and extracts music track metadata
2. **Process** - Generates AI embeddings using CLAP model for semantic understanding  
3. **Search** - Find music using natural language or audio file similarity
4. **Recommend** - Get AI-powered recommendations based on sound, mood, and style

**Architecture**: Python backend (FastAPI) + Next.js frontend + ChromaDB vector database

## Features

**🔍 Smart Search**
- Text search: "upbeat 80s synthpop", "melancholic indie rock"
- Audio search: Upload files to find similar tracks
- Browse library with AI recommendations

**🚀 Performance** 
- Distributed GPU processing for large libraries
- Resumable embedding generation
- Real-time progress tracking

**⚙️ Integration**
- Seamless Plex integration
- Modern web interface (Next.js + TypeScript)
- YAML configuration with platform-specific paths

## Setup

### Requirements
- Python 3.9+ and Node.js 18+
- Plex Media Server with music library
- GPU recommended for faster processing

### Installation

```bash
# 1. Clone and install backend
git clone https://github.com/marceljungle/mycelium.git
cd mycelium
pip install -e .

# 2. Setup configuration
mkdir -p ~/.config/mycelium
cp config.example.yml ~/.config/mycelium/config.yml
# Edit config.yml with your Plex token

# 3. Install frontend dependencies
cd frontend && npm install
```

### Quick Start

```bash
# Start server (API + Frontend)
mycelium server

# Or run separately
mycelium api &              # Backend only
cd frontend && npm run dev  # Frontend only

# For distributed processing (optional)
mycelium client --server-host 192.168.1.100  # On GPU machine
```

Visit `http://localhost:3000` for the web interface.

## Usage

### Basic Workflow

```bash
# 1. Scan your Plex library
mycelium scan

# 2. Generate AI embeddings (can take time for large libraries)
mycelium process

# 3. Start the web interface
mycelium server
```

### Command Line

```bash
mycelium scan                              # Scan Plex library
mycelium process                           # Generate embeddings (resumable)
mycelium search-text "melancholic rock"   # Text search
mycelium search-audio song.mp3            # Audio file search
mycelium stats                             # Show statistics
```

### Web Interface

**Search**: Natural language search ("upbeat indie rock") or upload audio files  
**Library**: Browse tracks and get AI recommendations  
**Settings**: Configure Plex connection and processing options

### Distributed Processing

For large libraries, use GPU workers for faster processing:

```bash
# On main server
mycelium server

# On GPU machine(s)  
mycelium client --server-host YOUR_SERVER_IP
```

## Configuration

Edit `~/.config/mycelium/config.yml` with your Plex token:

```yaml
plex:
  url: http://localhost:32400
  token: your_plex_token_here
  music_library_name: Music

api:
  host: 0.0.0.0
  port: 8000
```

**Platform paths**:
- Linux/macOS: `~/.config/mycelium/config.yml`
- Windows: `%APPDATA%\mycelium\config.yml`

## API Reference

**Library**: `/api/library/scan`, `/api/library/process`, `/api/library/stats`  
**Search**: `/api/search/text?q=query`, `/api/search/audio` (POST)  
**Workers**: `/workers/register`, `/workers/get_job`, `/workers/submit_result`

## Development

```bash
# Development setup
pip install -e ".[dev]"
cd frontend && npm install

# Code quality
black src/ && isort src/ && mypy src/
cd frontend && npm run lint && npm run build
```

## Project Structure

```
mycelium/
├── src/mycelium/           # Python backend (FastAPI + clean architecture)
│   ├── domain/             # Core business logic
│   ├── application/        # Use cases and services  
│   ├── infrastructure/     # External adapters (Plex, CLAP, ChromaDB)
│   ├── api/                # FastAPI endpoints
│   └── main.py             # CLI entry point
├── frontend/               # Next.js frontend (TypeScript + Tailwind)
│   └── src/components/     # React components
└── config.example.yml      # Configuration template
```

## Tips

- **Large libraries**: Use GPU workers (`mycelium client`) for faster processing
- **Plex token**: Get from Plex settings → Network → "Show Advanced" 
- **Resume processing**: Embedding generation can be stopped and resumed anytime
- **Performance**: Batch processing adapts to available memory automatically

## Contributing

Contributions welcome! Ensure changes follow existing patterns, include TypeScript types, and use the logging system.

## License

MIT License - see [LICENSE](LICENSE) file.

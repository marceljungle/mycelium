# Mycelium Configuration

Mycelium now supports both environment variables (.env files) and YAML configuration files.

## Configuration Priority

1. Environment variables (highest priority)
2. YAML configuration file
3. Default values (lowest priority)

## YAML Configuration

Place your configuration file at: `~/.config/mycelium/config.yml`

### Example Configuration

```yaml
# Plex server configuration
plex:
  url: http://localhost:32400
  token: your_plex_token_here
  music_library_name: Music

# CLAP model configuration  
clap:
  model_id: laion/larger_clap_music_and_speech
  target_sr: 48000
  chunk_duration_s: 10
  batch_size: 16

# ChromaDB vector database configuration
chroma:
  db_path: ./music_vector_db
  collection_name: my_music_library
  batch_size: 1000

# Track metadata database configuration
database:
  db_path: ./mycelium_tracks.db

# API server configuration
api:
  host: localhost
  port: 8000
  reload: false
```

## Environment Variables (Legacy Support)

You can still use environment variables or .env files:

```
PLEX_URL=http://localhost:32400
PLEX_TOKEN=your_plex_token_here
PLEX_MUSIC_LIBRARY=Music
API_HOST=localhost
API_PORT=8000
DATABASE_PATH=./mycelium_tracks.db
```

## New Workflow

### Separated Scanning and Processing

The new workflow separates library scanning from embedding processing:

1. **Scan Library**: `POST /api/library/scan`
   - Scans Plex library and saves track metadata to database
   - Includes `added_at` timestamps for incremental updates
   - Can be run multiple times to update track information

2. **Process Embeddings**: `POST /api/library/process` 
   - Processes embeddings for unprocessed tracks from database
   - Resumable - can be stopped and restarted
   - Progress tracking available

3. **Monitor Progress**: `GET /api/library/progress`
   - Get current processing statistics
   - Check how many tracks are processed vs. unprocessed

### API Endpoints

- `POST /api/library/scan` - Scan library and save to database
- `POST /api/library/process` - Process embeddings from database  
- `POST /api/library/process/stop` - Stop current processing
- `GET /api/library/progress` - Get processing progress
- `GET /api/library/can_resume` - Check if processing can be resumed
- `POST /api/library/process/legacy` - Old workflow (scan + process)

### Database Storage

Track metadata is now stored in SQLite database with:
- Track information (artist, album, title, filepath)
- Timestamps (added_at, last_scanned, processed_at)
- Processing status (processed/unprocessed)
- Session tracking for resumable operations
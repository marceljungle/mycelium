// ---------------------------------------------------------------------------
// Track / Search
// ---------------------------------------------------------------------------

export interface TrackResponse {
  artist: string;
  album: string;
  title: string;
  filepath: string;
  media_server_rating_key: string;
  media_server_type: string;
}

export interface SearchResultResponse {
  track: TrackResponse;
  similarity_score: number;
  distance: number;
}

export interface TracksListResponse {
  tracks: TrackResponse[];
  total_count: number;
  page: number;
  limit: number;
}

// ---------------------------------------------------------------------------
// Library operations
// ---------------------------------------------------------------------------

export interface TrackDatabaseStats {
  total_tracks: number;
  processed_tracks: number;
  unprocessed_tracks: number;
  progress_percentage: number;
  is_processing?: boolean;
  model_id?: string;
}

export interface LibraryStatsResponse {
  total_embeddings: number;
  collection_name: string;
  database_path: string;
  track_database_stats?: TrackDatabaseStats;
}

export interface ScanLibraryResponse {
  message: string;
  total_tracks: number;
  new_tracks: number;
  updated_tracks: number;
  scan_timestamp: string;
}

export interface ProcessingResponse {
  status: string;
  message?: string;
  task_id?: string;
  track_id?: string;
  query?: string;
  filename?: string;
  active_workers?: number;
  tasks_created?: number;
  confirmation_required?: boolean;
}

export interface StopProcessingResponse {
  message: string;
  type?: string;
  cleared_tasks?: number;
}

// ---------------------------------------------------------------------------
// Playlists
// ---------------------------------------------------------------------------

export interface CreatePlaylistRequest {
  name: string;
  track_ids: string[];
  batch_size?: number;
}

export interface PlaylistResponse {
  name: string;
  track_count: number;
  created_at: string;
  server_id?: string;
}

// ---------------------------------------------------------------------------
// Task queue
// ---------------------------------------------------------------------------

export interface TaskStatusResponse {
  task_id: string;
  status: string;
  track_id?: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  search_results?: SearchResultResponse[];
}

// ---------------------------------------------------------------------------
// Server config
// ---------------------------------------------------------------------------

export interface MediaServerSection { type: string }
export interface PlexSection { url: string; token?: string; music_library_name: string }
export interface ServerSection { gpu_batch_size: number }
export interface APISection { host: string; port: number; reload: boolean }
export interface ChromaSection { collection_name: string; batch_size: number }
export interface EmbeddingSection { type: string }
export interface ClapSection { model_id: string; target_sr: number; chunk_duration_s: number }
export interface MuqSection { model_id: string; target_sr: number; chunk_duration_s: number }
export interface LoggingSection { level: string }

export interface ConfigResponse {
  media_server: MediaServerSection;
  plex: PlexSection;
  server: ServerSection;
  api: APISection;
  chroma: ChromaSection;
  embedding: EmbeddingSection;
  clap: ClapSection;
  muq: MuqSection;
  logging: LoggingSection;
}

// Config request fields use `any` to match Python's Dict[str, Any] — configs are dynamic.
/* eslint-disable @typescript-eslint/no-explicit-any */
export interface ConfigRequest {
  media_server: Record<string, any>;
  plex: Record<string, any>;
  api: Record<string, any>;
  chroma: Record<string, any>;
  embedding?: Record<string, any>;
  clap: Record<string, any>;
  muq?: Record<string, any>;
  server: Record<string, any>;
  logging: Record<string, any>;
  database?: Record<string, any>;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

export interface SaveConfigResponse {
  message: string;
  status: string;
  reloaded: boolean;
  reload_error?: string;
}

// ---------------------------------------------------------------------------
// Capabilities
// ---------------------------------------------------------------------------

export interface CapabilitiesResponse {
  embedding_model_type: string;
  model_id: string;
  supports_text_search: boolean;
  supports_audio_search: boolean;
  supports_similar_tracks: boolean;
}

// ---------------------------------------------------------------------------
// Compute-on-server helpers
// ---------------------------------------------------------------------------

export interface ComputeOnServerRequest {
  track_id: string;
}

export interface ComputeTextSearchRequest {
  query: string;
  n_results?: number;
}

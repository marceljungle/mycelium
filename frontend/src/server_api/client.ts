import { API_BASE_URL } from '@/config/api';
import type {
  CapabilitiesResponse,
  ComputeOnServerRequest,
  ComputeTextSearchRequest,
  ConfigRequest,
  ConfigResponse,
  CreatePlaylistRequest,
  LibraryStatsResponse,
  PlaylistResponse,
  ProcessingResponse,
  SaveConfigResponse,
  ScanLibraryResponse,
  SearchResultResponse,
  StopProcessingResponse,
  TaskStatusResponse,
  TrackDatabaseStats,
  TracksListResponse,
} from './types';

// Re-export all types so consumers can `import { api, SearchResultResponse } from '@/server_api/client'`
export * from './types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, init);
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new ApiError(res.status, body || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

function qs(params: Record<string, string | number | undefined | null>): string {
  const entries = Object.entries(params).filter(
    ([, v]) => v != null && v !== ''
  );
  if (entries.length === 0) return '';
  return '?' + new URLSearchParams(
    entries.map(([k, v]) => [k, String(v)])
  ).toString();
}

// ---------------------------------------------------------------------------
// Server API
// ---------------------------------------------------------------------------

export const api = {
  // --- Capabilities ---
  getCapabilities(): Promise<CapabilitiesResponse> {
    return request('/api/capabilities');
  },

  // --- Library ---
  getLibraryStats(): Promise<LibraryStatsResponse> {
    return request('/api/library/stats');
  },

  getLibraryTracks(params: {
    page?: number;
    limit?: number;
    search?: string;
    artist?: string;
    album?: string;
    title?: string;
  } = {}): Promise<TracksListResponse> {
    return request(`/api/library/tracks${qs(params)}`);
  },

  scanLibrary(): Promise<ScanLibraryResponse> {
    return request('/api/library/scan', { method: 'POST' });
  },

  processLibrary(): Promise<ProcessingResponse> {
    return request('/api/library/process', { method: 'POST' });
  },

  processLibraryOnServer(): Promise<ProcessingResponse> {
    return request('/api/library/process/server', { method: 'POST' });
  },

  stopProcessing(): Promise<StopProcessingResponse> {
    return request('/api/library/process/stop', { method: 'POST' });
  },

  getProcessingProgress(params: { modelId?: string } = {}): Promise<TrackDatabaseStats> {
    return request(`/api/library/progress${qs({ model_id: params.modelId })}`);
  },

  // --- Search ---
  searchText(params: { q: string; nResults?: number }): Promise<ProcessingResponse> {
    return request(`/api/search/text${qs({ q: params.q, n_results: params.nResults })}`);
  },

  searchAudio(params: { audio?: Blob; nResults?: number } = {}): Promise<ProcessingResponse> {
    const form = new FormData();
    if (params.audio) form.append('audio', params.audio);
    if (params.nResults != null) form.append('n_results', String(params.nResults));
    return request('/api/search/audio', { method: 'POST', body: form });
  },

  computeTextSearch(params: {
    computeTextSearchRequest: ComputeTextSearchRequest;
  }): Promise<SearchResultResponse[]> {
    return request('/compute/search/text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params.computeTextSearchRequest),
    });
  },

  computeAudioSearch(params: {
    audio?: Blob;
    nResults?: number;
  } = {}): Promise<SearchResultResponse[]> {
    const form = new FormData();
    if (params.audio) form.append('audio', params.audio);
    if (params.nResults != null) form.append('n_results', String(params.nResults));
    return request('/compute/search/audio', { method: 'POST', body: form });
  },

  computeOnServer(params: {
    computeOnServerRequest: ComputeOnServerRequest;
  }): Promise<{ message?: string }> {
    return request('/compute/on_server', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params.computeOnServerRequest),
    });
  },

  // --- Similar tracks ---
  getSimilarByTrack(params: {
    trackId: string;
    nResults?: number;
  }): Promise<SearchResultResponse[] | ProcessingResponse> {
    const trackId = encodeURIComponent(params.trackId);
    return request(`/similar/by_track/${trackId}${qs({ n_results: params.nResults })}`);
  },

  // --- Task queue ---
  getTaskStatus(params: { taskId: string }): Promise<TaskStatusResponse> {
    const taskId = encodeURIComponent(params.taskId);
    return request(`/api/queue/task/${taskId}`);
  },

  // --- Config ---
  getConfig(): Promise<ConfigResponse> {
    return request('/api/config');
  },

  saveConfig(params: { configRequest: ConfigRequest }): Promise<SaveConfigResponse> {
    return request('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params.configRequest),
    });
  },

  // --- Playlists ---
  createPlaylist(params: {
    createPlaylistRequest: CreatePlaylistRequest;
  }): Promise<PlaylistResponse> {
    return request('/api/playlists/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params.createPlaylistRequest),
    });
  },
};

import { WORKER_API_BASE_URL } from '@/config/api';
import type {
  WorkerConfigRequest,
  WorkerConfigResponse,
  SaveConfigResponse,
  ClientStatusResponse,
  StopClientResponse,
} from './types';

// Re-export all types
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
  const res = await fetch(`${WORKER_API_BASE_URL}${path}`, init);
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new ApiError(res.status, body || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Worker API
// ---------------------------------------------------------------------------

export const workerApi = {
  getWorkerConfig(): Promise<WorkerConfigResponse> {
    return request('/api/config');
  },

  saveWorkerConfig(params: {
    workerConfigRequest: WorkerConfigRequest;
  }): Promise<SaveConfigResponse> {
    return request('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params.workerConfigRequest),
    });
  },

  getClientStatus(): Promise<ClientStatusResponse> {
    return request('/api/status');
  },

  stopProcessing(): Promise<StopClientResponse> {
    return request('/api/stop', { method: 'POST' });
  },
};

// ---------------------------------------------------------------------------
// Worker config sections
// ---------------------------------------------------------------------------

export interface WorkerClientSection {
  server_host: string;
  server_port: number;
  download_queue_size: number;
  job_queue_size: number;
  poll_interval: number;
  download_workers: number;
  gpu_batch_size: number;
}

export interface WorkerClientAPISection {
  host: string;
  port: number;
}

export interface WorkerEmbeddingSection {
  type: string;
}

export interface WorkerClapSection {
  model_id: string;
  target_sr: number;
  chunk_duration_s: number;
}

export interface WorkerMuqSection {
  model_id: string;
  target_sr: number;
  chunk_duration_s: number;
}

export interface WorkerLoggingSection {
  level: string;
}

// ---------------------------------------------------------------------------
// Worker config request / response
// ---------------------------------------------------------------------------

export interface WorkerConfigResponse {
  client: WorkerClientSection;
  client_api: WorkerClientAPISection;
  embedding: WorkerEmbeddingSection;
  clap: WorkerClapSection;
  muq: WorkerMuqSection;
  logging: WorkerLoggingSection;
}

// Config request fields use `any` to match Python's Dict[str, Any] — configs are dynamic.
/* eslint-disable @typescript-eslint/no-explicit-any */
export interface WorkerConfigRequest {
  client: Record<string, any>;
  client_api: Record<string, any>;
  embedding?: Record<string, any>;
  clap: Record<string, any>;
  muq?: Record<string, any>;
  logging: Record<string, any>;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

export interface SaveConfigResponse {
  message: string;
  status: string;
  reloaded: boolean;
  reload_error?: string;
}

// ---------------------------------------------------------------------------
// Client status (GET /api/status)
// ---------------------------------------------------------------------------

export interface WorkerProcessingStatus {
  is_running: boolean;
  is_processing: boolean;
  jobs_in_download_queue: number;
  jobs_ready_for_gpu: number;
  total_jobs_processed: number;
  current_batch_size: number;
  last_job_completed_at: number | null;
  worker_id: string | null;
  server_url: string | null;
}

export interface ClientStatusResponse {
  server_reachable: boolean;
  worker: WorkerProcessingStatus;
}

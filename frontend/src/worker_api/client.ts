// OpenAPI generated client wrapper for Worker API
// Centralizes configuration and exports a ready-to-use API instance.
import { Configuration, DefaultApi } from './generated';
import { WORKER_API_BASE_URL } from '@/config/api';

export const workerApiConfig = new Configuration({ basePath: WORKER_API_BASE_URL });

export * from './generated';

export const workerApi = new DefaultApi(workerApiConfig);

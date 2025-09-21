// OpenAPI generated client wrapper
// Centralizes configuration and exports a ready-to-use API instance.
import { Configuration } from './generated';
import { DefaultApi } from './generated';
import { API_BASE_URL } from '@/config/api';

export const apiConfig = new Configuration({ basePath: API_BASE_URL });

export * from './generated';

export const api = new DefaultApi(apiConfig);

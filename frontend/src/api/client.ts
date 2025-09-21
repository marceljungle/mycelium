// OpenAPI generated client wrapper
// Centralizes configuration and exports a ready-to-use API instance.
import { Configuration } from './generated';
import { API_BASE_URL } from '@/config/api';

export const apiConfig = new Configuration({ basePath: API_BASE_URL });

// The generated folder exports each API class separately based on tags or DefaultApi.
// Prefer DefaultApi when available; otherwise, import the specific API classes you need.
export * from './generated';

// Example: consumers can do `new DefaultApi(apiConfig)` or import specific APIs.

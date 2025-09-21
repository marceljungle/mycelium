// Type shims to re-export generated OpenAPI DTOs.
// This preserves existing import paths while sourcing types from `openapi.d.ts`.
import type { components } from './openapi';

export type ProcessingResponse = components['schemas']['ProcessingResponse'];

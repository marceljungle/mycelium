// Type shims to re-export generated OpenAPI DTOs.
// This preserves existing import paths while sourcing types from the generated client.
// All types are re-exported directly from `@/api/generated/models`.

export type {
	ProcessingResponse,
	TrackResponse,
	SearchResultResponse,
	TracksListResponse,
	LibraryStatsResponse,
	TaskStatusResponse,
	ConfigResponse,
	SaveConfigResponse,
} from '@/api/generated/models';

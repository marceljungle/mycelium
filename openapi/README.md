# OpenAPI schema and client generation

This folder hosts the OpenAPI contract and code generation scripts for frontend (TypeScript) and optional clients.

Recommended approach (API-first)
- Source of truth: `openapi/spec.yaml` is the contract authority for both backend and frontend.
- Generate clients/types: use popular generators
  - Frontend: openapi-typescript (types-only) or openapi-generator (typescript-fetch/axios clients)
  - Python: optional via openapi-generator or other tools

Why this approach?
- Single contract reduces drift between backend and frontend
- Enables CI checks and codegen without booting the app
- Easier to review/PR API changes

## Files
- `spec.yaml`: OpenAPI 3.1 contract (authoritative)
- `generate.sh`: Script to generate clients/types from `spec.yaml`
- `export_schema.py`: Legacy helper to export schema from FastAPI for comparison
- `schema.json`: Legacy exported schema (generated)
- `frontend-types/`: Optional TS client output (git-ignored recommended)
- `python-client/`: Optional Python client output (git-ignored recommended)

## Usage (API-first)

### Prerequisites
- Node.js for frontend types generation

### 1) Edit the API
Propose changes in `openapi/spec.yaml`. Keep enums/fields aligned with backend models (e.g., `ProcessingResponse.status`).

### 2) Generate TypeScript types for the frontend
Using openapi-typescript (types only):
```bash
cd frontend
npm run openapi:types
```

Or using openapi-generator to generate a TS client (optional):
```bash
npx @openapitools/openapi-generator-cli generate \
  -i ../openapi/spec.yaml \
  -g typescript-fetch \
  -o src/api-client
```

## Legacy backend-first export (optional)
From repo root, export the schema from FastAPI to compare against spec:
```bash
python openapi/export_schema.py --out openapi/schema.json
npx openapi-typescript openapi/schema.json -o frontend/src/types/openapi.d.ts
```

## CI suggestions
- Add a workflow step to validate `openapi/spec.yaml` (e.g., `swagger-cli validate`).
- Run `bash openapi/generate.sh` and verify `frontend` builds: `npm run build`.

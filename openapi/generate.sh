#!/usr/bin/env bash
set -euo pipefail

# Generate OpenAPI-based client types from API-first spec
# Usage: from repo root: bash openapi/generate.sh

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SERVER_SPEC="$ROOT_DIR/openapi/server_openapi.yaml"
WORKER_SPEC="$ROOT_DIR/openapi/worker_openapi.yaml"

if [ ! -f "$SERVER_SPEC" ]; then
  echo "Server spec not found at: $SERVER_SPEC"
  exit 1
fi

## Always attempt to generate both server and worker clients

# Generate TypeScript Fetch client using openapi-generator
if command -v npx >/dev/null 2>&1; then
  echo "Generating TypeScript Fetch client (server) from $SERVER_SPEC ..."
  SERVER_OUT_DIR="$ROOT_DIR/frontend/src/server_api/generated"
  rm -rf "$SERVER_OUT_DIR"
  npx @openapitools/openapi-generator-cli generate \
    -i "$SERVER_SPEC" \
    -g typescript-fetch \
    -o "$SERVER_OUT_DIR" \
    --additional-properties=supportsES6=true,typescriptThreePlus=true

  echo "Generating TypeScript Fetch client (worker) from $WORKER_SPEC ..."
  WORKER_OUT_DIR="$ROOT_DIR/frontend/src/worker_api/generated"
  rm -rf "$WORKER_OUT_DIR"
  npx @openapitools/openapi-generator-cli generate \
    -i "$WORKER_SPEC" \
    -g typescript-fetch \
    -o "$WORKER_OUT_DIR" \
    --additional-properties=supportsES6=true,typescriptThreePlus=true
else
  echo "npx not found. Please install Node.js and ensure npx is available to generate TS client."
fi

# Generate Python Pydantic (models-only) for server and worker (API-first contracts)
if command -v npx >/dev/null 2>&1; then
  echo "Preparing Python generation directories (models-only)..."
  PY_GEN_BASE="$ROOT_DIR/src/mycelium/api/generated_sources"
  mkdir -p "$PY_GEN_BASE"
  # Keep package marker so imports like mycelium.api.generated_sources.* work
  if [ ! -f "$PY_GEN_BASE/__init__.py" ]; then
    echo "# Auto-generated package marker for generated API sources" > "$PY_GEN_BASE/__init__.py"
  fi

  # Clean previous generated client and schema packages
  rm -rf "$ROOT_DIR/src/mycelium/api/generated_sources/server_client"
  rm -rf "$ROOT_DIR/src/mycelium/api/generated_sources/worker_client"
  rm -rf "$ROOT_DIR/src/mycelium/api/generated_sources/server_schemas"
  rm -rf "$ROOT_DIR/src/mycelium/api/generated_sources/worker_schemas"

  echo "Generating Python Pydantic v1 models (server) from $SERVER_SPEC ..."
  # Note: output is set to src root so the package gets created under the correct nested path
  npx @openapitools/openapi-generator-cli generate \
    -i "$SERVER_SPEC" \
    -g python-pydantic-v1 \
    -o "$ROOT_DIR/src" \
    --additional-properties=packageName=mycelium.api.generated_sources.server_schemas,projectName=MyceliumServerSchemas,packageVersion=0.1.0,generateSourceCodeOnly=true,pythonVersion=3.9

  echo "Generating Python Pydantic v1 models (worker) from $WORKER_SPEC ..."
  npx @openapitools/openapi-generator-cli generate \
    -i "$WORKER_SPEC" \
    -g python-pydantic-v1 \
    -o "$ROOT_DIR/src" \
    --additional-properties=packageName=mycelium.api.generated_sources.worker_schemas,projectName=MyceliumWorkerSchemas,packageVersion=0.1.0,generateSourceCodeOnly=true,pythonVersion=3.9
else
  echo "npx not found. Skipping Python models generation."
fi
echo "OpenAPI generation complete."

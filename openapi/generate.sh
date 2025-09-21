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
  SERVER_OUT_DIR="$ROOT_DIR/frontend/src/api/generated"
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

# Optional: generate Python client (uncomment to use)
# npx @openapitools/openapi-generator-cli generate \
#   -i "$INPUT_SPEC" \
#   -g python \
#   -o "$ROOT_DIR/openapi/python-client"

echo "OpenAPI generation complete."

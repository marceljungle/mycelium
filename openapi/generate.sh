#!/usr/bin/env bash
set -euo pipefail

# Generate OpenAPI-based client types from API-first spec
# Usage: from repo root: bash openapi/generate.sh

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SPEC_YAML="$ROOT_DIR/openapi/spec.yaml"
SPEC_YML="$ROOT_DIR/openapi/spec.yml"

INPUT_SPEC=""
if [ -f "$SPEC_YAML" ]; then
  INPUT_SPEC="$SPEC_YAML"
elif [ -f "$SPEC_YML" ]; then
  INPUT_SPEC="$SPEC_YML"
else
  echo "Spec not found. Expected at: $SPEC_YAML or $SPEC_YML"
  exit 1
fi

# Generate TS types (requires npx openapi-typescript installed or available)
if command -v npx >/dev/null 2>&1; then
  echo "Generating TypeScript types from $INPUT_SPEC ..."
  npx openapi-typescript "$INPUT_SPEC" -o "$ROOT_DIR/frontend/src/types/openapi.d.ts"
else
  echo "npx not found. Please install Node.js and ensure npx is available to generate TS types."
fi

# Optional: generate TS client using openapi-generator (uncomment to use)
# npx @openapitools/openapi-generator-cli generate \
#   -i "$INPUT_SPEC" \
#   -g typescript-fetch \
#   -o "$ROOT_DIR/openapi/frontend-types"

# Optional: generate Python client (uncomment to use)
# npx @openapitools/openapi-generator-cli generate \
#   -i "$INPUT_SPEC" \
#   -g python \
#   -o "$ROOT_DIR/openapi/python-client"

echo "OpenAPI generation complete. Types written to frontend/src/types/openapi.d.ts"

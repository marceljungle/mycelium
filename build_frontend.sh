#!/bin/bash

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
FRONTEND_DIR="$ROOT_DIR/frontend"
SERVER_DIST_DIR="$ROOT_DIR/backend/mycelium/frontend_dist"
SERVER_OUT_DIR="$FRONTEND_DIR/out"

echo "Building Next.js frontend..."

echo "Running Next.js build (server mode)..."
npm run build --prefix "$FRONTEND_DIR"

if [ -d "$SERVER_DIST_DIR" ]; then
    echo "Removing existing frontend_dist directory..."
    rm -rf "$SERVER_DIST_DIR"
fi

echo "Creating new frontend_dist directory..."
mkdir -p "$SERVER_DIST_DIR"

echo "Copying frontend build output to backend/mycelium/frontend_dist..."
cp -a "$SERVER_OUT_DIR"/. "$SERVER_DIST_DIR"/

echo "Frontend build completed successfully!"
echo "Static files are now available in backend/mycelium/frontend_dist/"
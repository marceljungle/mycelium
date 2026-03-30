#!/bin/bash

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
FRONTEND_DIR="$ROOT_DIR/frontend"
CLIENT_DIST_DIR="$ROOT_DIR/backend/mycelium/client_frontend_dist"
CLIENT_OUT_DIR="$FRONTEND_DIR/out"

echo "Building Next.js frontend for client mode..."

export NEXT_PUBLIC_MYCELIUM_MODE=client

echo "Running Next.js build (client mode)..."
npm run build --prefix "$FRONTEND_DIR"

if [ -d "$CLIENT_DIST_DIR" ]; then
    echo "Removing existing client_frontend_dist directory..."
    rm -rf "$CLIENT_DIST_DIR"
fi

echo "Creating new client_frontend_dist directory..."
mkdir -p "$CLIENT_DIST_DIR"

echo "Copying client frontend build output to backend/mycelium/client_frontend_dist..."
cp -a "$CLIENT_OUT_DIR"/. "$CLIENT_DIST_DIR"/

echo "Client frontend build completed successfully!"
echo "Client static files are now available in backend/mycelium/client_frontend_dist/"
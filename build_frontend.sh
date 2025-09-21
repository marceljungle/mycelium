#!/bin/bash

echo "Building Next.js frontend..."

# Generate OpenAPI clients (server and worker) before building
echo "Generating OpenAPI clients (server and worker)..."
if ! npm run openapi:generate --prefix frontend; then
    echo "Error: OpenAPI client generation failed"
    exit 1
fi

# Build main server frontend (without client mode)
if ! npm run build --prefix frontend; then
    echo "Error: Frontend build failed"
    exit 1
fi

# Remove existing frontend_dist directory if it exists
if [ -d "src/mycelium/frontend_dist" ]; then
    echo "Removing existing frontend_dist directory..."
    rm -rf src/mycelium/frontend_dist
fi

# Create new frontend_dist directory
echo "Creating new frontend_dist directory..."
mkdir -p src/mycelium/frontend_dist

# Copy all contents from frontend/out/ to src/mycelium/frontend_dist
echo "Copying frontend build output to src/mycelium/frontend_dist..."
cp -r frontend/out/* src/mycelium/frontend_dist/

echo "Frontend build completed successfully!"
echo "Static files are now available in src/mycelium/frontend_dist/"

# Also build client frontend
echo ""
echo "Building client frontend..."
./build_client_frontend.sh
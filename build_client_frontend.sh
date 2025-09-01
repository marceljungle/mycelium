#!/bin/bash

echo "Building Next.js frontend for client mode..."

# Set environment variable for client mode
export NEXT_PUBLIC_MYCELIUM_MODE=client

# Run the Next.js build command with client mode
if ! NEXT_PUBLIC_MYCELIUM_MODE=client npm run build --prefix frontend; then
    echo "Error: Client frontend build failed"
    exit 1
fi

# Remove existing client_frontend_dist directory if it exists
if [ -d "src/mycelium/client_frontend_dist" ]; then
    echo "Removing existing client_frontend_dist directory..."
    rm -rf src/mycelium/client_frontend_dist
fi

# Create new client_frontend_dist directory
echo "Creating new client_frontend_dist directory..."
mkdir -p src/mycelium/client_frontend_dist

# Copy all contents from frontend/out/ to src/mycelium/client_frontend_dist
echo "Copying client frontend build output to src/mycelium/client_frontend_dist..."
cp -r frontend/out/* src/mycelium/client_frontend_dist/

echo "Client frontend build completed successfully!"
echo "Client static files are now available in src/mycelium/client_frontend_dist/"
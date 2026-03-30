#!/bin/bash

set -e

mkdir -p build/wheels

echo "Cleaning previous builds..."
rm -rf build/lib
rm -rf build/bdist.*
rm -rf backend/mycelium.egg-info

echo "Building wheel..."
pip wheel . --wheel-dir build/wheels

echo "Wheel built successfully in build/wheels/"

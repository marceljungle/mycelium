#!/bin/bash

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

DO_SERVER_FRONTEND=1
DO_CLIENT_FRONTEND=1
DO_PYTHON_BUILD=0

usage() {
  cat <<'EOF'
Usage: ./build.sh [options]

Runs the full Mycelium build workflow. By default this script builds both
frontend bundles and stops before packaging Python artifacts. Pass --with-wheel
to invoke the Python build as well.

Options:
  --skip-server-frontend   Skip building the server-mode frontend
  --skip-client-frontend   Skip building the client-mode frontend
  --skip-frontends         Skip both frontend builds
  --with-wheel             Build Python artifacts using `python -m build`
  -h, --help               Show this help message and exit
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-server-frontend)
      DO_SERVER_FRONTEND=0
      ;;
    --skip-client-frontend)
      DO_CLIENT_FRONTEND=0
      ;;
    --skip-frontends)
      DO_SERVER_FRONTEND=0
      DO_CLIENT_FRONTEND=0
      ;;
    --with-wheel)
      DO_PYTHON_BUILD=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

if (( DO_SERVER_FRONTEND )); then
  echo "Building server frontend..."
  bash "$ROOT_DIR/build_frontend.sh"
else
  echo "Skipping server frontend build"
fi

if (( DO_CLIENT_FRONTEND )); then
  echo "Building client frontend..."
  bash "$ROOT_DIR/build_client_frontend.sh"
else
  echo "Skipping client frontend build"
fi

if (( DO_PYTHON_BUILD )); then
  echo "Building Python package..."
  python3 -m build
else
  echo "Skipping Python packaging"
fi

echo "Build workflow completed successfully."

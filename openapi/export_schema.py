#!/usr/bin/env python3
"""
Export OpenAPI schema JSON from the FastAPI app without starting the server.

Usage:
  python openapi/export_schema.py --out openapi/schema.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Export OpenAPI schema from FastAPI app")
    parser.add_argument("--out", type=str, default="openapi/schema.json", help="Output file path")
    args = parser.parse_args()

    # Import the app lazily to avoid side effects
    from src.mycelium.api.app import app  # type: ignore

    schema = app.openapi()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(schema, indent=2))

    print(f"Wrote OpenAPI schema to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

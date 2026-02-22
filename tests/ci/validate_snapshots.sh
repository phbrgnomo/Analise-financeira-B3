#!/usr/bin/env bash
set -euo pipefail

# Run snapshot validation script for CI and local use.
# Uses SNAPSHOT_DIR if set, otherwise falls back to repository `snapshots`.

cd "$(dirname "$0")/../.."

SNAPSHOT_DIR="${SNAPSHOT_DIR:-snapshots}"
MANIFEST_PATH="${SNAPSHOT_DIR}/checksums.json"

if command -v poetry >/dev/null 2>&1; then
  poetry run python scripts/validate_snapshots.py --dir "$SNAPSHOT_DIR" --manifest "$MANIFEST_PATH"
else
  python3 scripts/validate_snapshots.py --dir "$SNAPSHOT_DIR" --manifest "$MANIFEST_PATH"
fi

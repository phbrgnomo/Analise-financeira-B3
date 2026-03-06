#!/usr/bin/env bash
set -euo pipefail

# Run snapshot validation script for CI and local use.
# Uses SNAPSHOT_DIR if set, otherwise falls back to `snapshots_test`.
# The canonical manifest remains versioned at `snapshots/checksums.json`.

cd "$(dirname "$0")/../.."

SNAPSHOT_DIR="${SNAPSHOT_DIR:-snapshots_test}"
MANIFEST_PATH="${MANIFEST_PATH:-snapshots/checksums.json}"

# If validating snapshots outside the repository `snapshots/` folder, allow external
# paths so the validation script doesn't refuse to write/resolve manifest paths.
ALLOW_EXTERNAL_FLAG=""
FLAGS=()
if [ "$SNAPSHOT_DIR" != "snapshots" ]; then
  ALLOW_EXTERNAL_FLAG="--allow-external"
  FLAGS+=("--allow-external")
fi

if command -v poetry >/dev/null 2>&1; then
  poetry run python scripts/validate_snapshots.py "${FLAGS[@]}" --dir "$SNAPSHOT_DIR" --manifest "$MANIFEST_PATH"
else
  python3 scripts/validate_snapshots.py "${FLAGS[@]}" --dir "$SNAPSHOT_DIR" --manifest "$MANIFEST_PATH"
fi

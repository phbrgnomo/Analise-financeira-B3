#!/usr/bin/env bash
set -euo pipefail

# Integration tests runner for CI and local use. Mirrors the `integration` job in .github/workflows/ci.yml
# Uses SNAPSHOT_DIR for snapshot output when set.

cd "$(dirname "$0")/../.."

SNAPSHOT_DIR="${SNAPSHOT_DIR:-$(mktemp -d)}"
export SNAPSHOT_DIR

if command -v poetry >/dev/null 2>&1; then
  poetry run pytest -q tests/integration -k quickstart_mocked --maxfail=1
  poetry run python scripts/generate_ci_snapshot.py
  poetry run python scripts/validate_snapshots.py --dir "$SNAPSHOT_DIR" --manifest snapshots/checksums.json --allow-external
else
  pytest -q tests/integration -k quickstart_mocked --maxfail=1
  python3 scripts/generate_ci_snapshot.py
  python3 scripts/validate_snapshots.py --dir "$SNAPSHOT_DIR" --manifest snapshots/checksums.json --allow-external
fi

echo "Integration snapshots (if any) may be under: $SNAPSHOT_DIR"

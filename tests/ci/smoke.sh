#!/usr/bin/env bash
set -euo pipefail

# Simple CI helper used by workflows: run tests and exit with pytest status
# Expected to be committed so CI workflows can call it reliably.

# Run from repo root
cd "$(dirname "$0")/../.."

# Prefer poetry if available
if command -v poetry >/dev/null 2>&1; then
	poetry run pytest -q
else
	pytest -q
fi

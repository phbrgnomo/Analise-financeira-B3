#!/usr/bin/env bash
set -euo pipefail

# Smoke test entrypoint used by CI
# Should run a minimal, fast check that verifies the app can import and run a trivial command.

python -m pytest tests -q -k "smoke or not integration" || exit 1

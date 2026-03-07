#!/usr/bin/env bash
set -euo pipefail

# Test runner for CI and local use. Mirrors the `test` job in .github/workflows/ci.yml
# Produces junit xml under reports/ for CI consumption.

cd "$(dirname "$0")/../.."

mkdir -p reports

if command -v poetry >/dev/null 2>&1; then
  poetry run pytest -q --maxfail=1 --junitxml=reports/junit.xml
else
  pytest -q --maxfail=1 --junitxml=reports/junit.xml
fi

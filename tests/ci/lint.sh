#!/usr/bin/env bash
set -euo pipefail

# Lint runner for CI and local use. Mirrors the `lint` job in .github/workflows/ci.yml
# Runs pre-commit (all files) and ruff check.

cd "$(dirname "$0")/../.."

if command -v poetry >/dev/null 2>&1; then
  poetry run pre-commit run --all-files --show-diff-on-failure
  poetry run ruff check . --show-files
else
  pre-commit run --all-files --show-diff-on-failure
  ruff check . --show-files
fi

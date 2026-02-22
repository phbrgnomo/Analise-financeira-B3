#!/usr/bin/env bash
set -euo pipefail

# Orquestrador simples para executar a pipeline de testes localmente ou em CI.
# Executa: lint -> test -> smoke -> integration
# Usa os scripts em tests/ci/ e respeita SNAPSHOT_DIR quando fornecido.

cd "$(dirname "$0")/../.."

function _err() {
  echo "CI Orchestrator: stage failed on $(date -u)" >&2
}

trap _err ERR


echo "CI Orchestrator: starting at $(date -u)"

echo "[1/5] Lint"
bash tests/ci/lint.sh

echo "[2/5] Unit tests"
bash tests/ci/test.sh

echo "[3/5] Smoke"
bash tests/ci/smoke.sh

echo "[4/5] Integration"
# Ensure SNAPSHOT_DIR is exported for the integration step (mirrors workflow)
export SNAPSHOT_DIR="${SNAPSHOT_DIR:-$(mktemp -d)}"
bash tests/ci/integration.sh

echo "[5/5] Validate snapshots"
# Validate committed repository snapshots (do not validate temp SNAPSHOT_DIR)
SNAPSHOT_DIR="snapshots" bash tests/ci/validate_snapshots.sh

echo "CI Orchestrator: all stages passed at $(date -u)"

exit 0

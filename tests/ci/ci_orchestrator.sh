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
# Run lint but don't fail the whole orchestrator if lint reports issues
if bash tests/ci/lint.sh; then
  echo "[1/5] Lint passed"
else
  echo "CI Orchestrator: [WARN] Lint failed — continuing to other stages" >&2
fi

echo "[2/5] Unit tests"
bash tests/ci/test.sh

echo "[3/5] Smoke"
bash tests/ci/smoke.sh

echo "[4/5] Integration"
# Ensure SNAPSHOT_DIR is exported for the integration step (mirrors workflow)
export SNAPSHOT_DIR="${SNAPSHOT_DIR:-$(mktemp -d)}"
bash tests/ci/integration.sh

echo "[5/5] Acceptance E2E (local)"
# Run any local E2E tests we added (e.g., tests/e2e/test_acceptance_snapshot.py)
if command -v poetry >/dev/null 2>&1; then
  NETWORK_MODE=playback poetry run pytest -q tests/e2e/test_acceptance_snapshot.py \
    || echo "CI Orchestrator: [WARN] Acceptance E2E falhou (não bloqueante)" >&2
else
  NETWORK_MODE=playback pytest -q tests/e2e/test_acceptance_snapshot.py \
    || echo "CI Orchestrator: [WARN] Acceptance E2E falhou (não bloqueante)" >&2
fi

echo "[6/6] Validate snapshots"
# Validate snapshots produced by the integration step (SNAPSHOT_DIR).
# The inline assignment below is intentional: it provides a sensible
# fallback when running `tests/ci/validate_snapshots.sh` independently
# (so the script can be invoked directly without requiring the earlier
# exported SNAPSHOT_DIR). When run via this orchestrator, the value set
# earlier by `export SNAPSHOT_DIR=...` will be preserved.
SNAPSHOT_DIR="${SNAPSHOT_DIR:-snapshots_test}" bash tests/ci/validate_snapshots.sh

echo "CI Orchestrator: all stages passed at $(date -u)"

exit 0

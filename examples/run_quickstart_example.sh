#!/usr/bin/env bash
# Quickstart runner (CI-friendly, deterministic, fixture-based)
#
# This script is intended to be a lightweight example that:
#   - Runs the main pipeline in `--no-network` mode using a deterministic fixture
#   - Writes a snapshot under `SNAPSHOT_DIR` (defaults to ./snapshots)
#   - Writes a run log under `LOG_DIR` (defaults to ./logs)
#   - Optionally writes command output to `OUTPUTS_DIR` (defaults to ./outputs)
#
# Expected usage:
#   examples/run_quickstart_example.sh --no-network --format json

set -euo pipefail

# Defaults (can be overridden via env vars)
DATA_DIR=${DATA_DIR:-./dados}
SNAPSHOT_DIR=${SNAPSHOT_DIR:-./snapshots}
OUTPUTS_DIR=${OUTPUTS_DIR:-./outputs}
LOG_DIR=${LOG_DIR:-./logs}

TICKER="PETR4.SA"
FORMAT="json"
NO_NETWORK=1
SAMPLE_TICKERS=
CONFIG_FILE=

usage(){
  cat <<'EOF'
Usage: $0 [--no-network] [--network] [--ticker TICKER] [--format json|text] [--sample-tickers FILE] [--config FILE]

Options:
  --no-network          Run without network access (default, uses deterministic fixtures)
  --network             Allow network access (overrides --no-network)
  --ticker TICKER       Ticker to run (default PETR4.SA)
  --format json|text    Output format (default: json)
  --sample-tickers FILE Use this file (one ticker per line) instead of the default fixture
  --config FILE         Source environment variables from a file (e.g. .env)
  --help, -h            Show this help message
EOF
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-network)
      NO_NETWORK=1
      shift
      ;;
    --network)
      NO_NETWORK=0
      shift
      ;;
    --ticker)
      TICKER="$2"
      shift 2
      ;;
    --format)
      FORMAT="$2"
      shift 2
      ;;
    --sample-tickers)
      SAMPLE_TICKERS="$2"
      shift 2
      ;;
    --config)
      CONFIG_FILE="$2"
      shift 2
      ;;
    --help|-h)
      usage
      ;;
    *)
      echo "Unknown arg: $1"
      usage
      ;;
  esac
done

# If configured, source env vars from a file (e.g. .env).
if [[ -n "$CONFIG_FILE" ]]; then
  if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Config file not found: $CONFIG_FILE" >&2
    exit 2
  fi
  # shellcheck disable=SC1090
  set -a
  source "$CONFIG_FILE"
  set +a
fi

mkdir -p "$SNAPSHOT_DIR" "$LOG_DIR"
if [ -n "$OUTPUTS_DIR" ]; then
  mkdir -p "$OUTPUTS_DIR"
fi

# Export key dirs so underlying CLI uses the same paths.
export DATA_DIR SNAPSHOT_DIR LOG_DIR OUTPUTS_DIR

JOB_ID=$(uuidgen 2>/dev/null || date +%s)
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOGFILE="$LOG_DIR/run_quickstart_${TIMESTAMP}.log"

echo "job_id=$JOB_ID ticker=$TICKER no_network=$NO_NETWORK" > "$LOGFILE"
echo "Running quickstart example for $TICKER (no_network=$NO_NETWORK)..." >> "$LOGFILE"

# Build base command and append conditional flags to avoid duplication.
## Prefer `poetry run main` when available, fallback to python module if not.
if command -v poetry >/dev/null 2>&1; then
  CMD=(poetry run main)
else
  # Resolve qual módulo Python usar como entrypoint.
  resolve_entrypoint() {
    python - "$@" <<'PY' 2>/dev/null
import importlib
import sys
for candidate in ("main", "src.main"):
    try:
        importlib.import_module(candidate)
    except Exception:
        continue
    else:
        print(candidate)
        sys.exit(0)
sys.exit(1)
PY
  }

  # Fallback JSON escaping for when neither jq nem python estão disponíveis.
  json_escape() {
    local escaped="${1//\\/\\\\}"
    escaped="${escaped//\"/\\\"}"
    escaped="${escaped//$'\n'/\\n}"
    escaped="${escaped//$'\r'/\\r}"
    escaped="${escaped//$'\t'/\\t}"
    escaped="${escaped//$'\b'/\\b}"
    escaped="${escaped//$'\f'/\\f}"
    printf '%s' "$escaped"
  }

  entrypoint_module="$(resolve_entrypoint)" || {
    echo "Error: could not find a Python entrypoint module (tried 'main' and 'src.main')." >&2
    exit 1
  }

  CMD=(python -m "$entrypoint_module")
fi
CMD+=(--ticker "$TICKER")
CMD+=(--format "$FORMAT")
if [[ $NO_NETWORK -eq 1 ]]; then
  CMD+=(--no-network)
  if [[ -z "$SAMPLE_TICKERS" ]]; then
    SAMPLE_TICKERS="tests/fixtures/sample_ticker.csv"
  fi
fi
if [[ -n "$SAMPLE_TICKERS" ]]; then
  CMD+=(--sample-tickers "$SAMPLE_TICKERS")
fi

# Execute the command capturing stdout for later summary extraction.
set +e
CMD_OUTPUT=$("${CMD[@]}" 2>>"$LOGFILE")
EXIT_CODE=$?
set -e

# Log the CLI output, and optionally persist it to OUTPUTS_DIR for inspection.
echo "$CMD_OUTPUT" >> "$LOGFILE"
if [ -n "$OUTPUTS_DIR" ]; then
  echo "$CMD_OUTPUT" > "$OUTPUTS_DIR/quickstart_${TIMESTAMP}.out"
fi

if [[ $EXIT_CODE -ne 0 ]]; then
  # Ensure we always emit a JSON summary on failure for CI
  FALLBACK_SUMMARY=$(
    jq -n --arg j "$JOB_ID" '{job_id:$j,status:"failure"}' 2>/dev/null ||
      echo "{\"job_id\":\"$JOB_ID\",\"status\":\"failure\"}"
  )
  echo "$FALLBACK_SUMMARY" >> "$LOGFILE"
  echo "$FALLBACK_SUMMARY"
  echo "Script failed; see $LOGFILE" >&2
  exit $EXIT_CODE
fi

# Derive a compact summary (JSON) from the CLI output when JSON mode is active.
SUMMARY="$CMD_OUTPUT"
# If JSON requested, try to parse CLI output; otherwise produce a defensive fallback JSON.
if [[ "$FORMAT" == "json" ]]; then
  export CMD_OUTPUT
  PARSED=$(python - <<'PY'
import json, os, sys
raw = os.environ.get('CMD_OUTPUT', '')
out = {'job_id': None, 'status': None, 'elapsed_sec': None, 'snapshot': None, 'rows': None}
try:
    data = json.loads(raw)
    out['job_id'] = data.get('job_id')
    out['status'] = data.get('status')
    out['elapsed_sec'] = data.get('duration_sec')
    tickers = data.get('tickers') or []
    if tickers:
        first = tickers[0]
        out['snapshot'] = first.get('snapshot_path')
        out['rows'] = first.get('rows_ingested') or first.get('rows')
except Exception:
    # parsing failed, leave as-is; we'll produce a fallback later
    pass
print(json.dumps(out, separators=(',', ':')))
PY
  ) || PARSED="{}"
  unset CMD_OUTPUT
  SUMMARY="$PARSED"
fi

# Post-process: ensure a snapshot checksum sidecar exists. If CLI didn't
# generate a .checksum, compute SHA256 for the most-recent CSV matching the
# ticker under SNAPSHOT_DIR and write the sidecar file.
if [[ -d "$SNAPSHOT_DIR" ]]; then
  # find newest csv for ticker pattern (allow both with/without .SA suffix)
  BASE_TICKER=$(echo "$TICKER" | sed 's/\.SA$//')
  LATEST_CSV=$(ls -1t "$SNAPSHOT_DIR"/*${BASE_TICKER}*.csv 2>/dev/null | head -n1 || true)
  if [[ -n "$LATEST_CSV" ]]; then
    CHECKSUM_PATH="${LATEST_CSV}.checksum"
    if [[ ! -f "$CHECKSUM_PATH" ]]; then
      if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$LATEST_CSV" | awk '{print $1}' > "$CHECKSUM_PATH"
      else
        # fallback to python
        # Pass the filename as an argument so sys.argv[1] is defined.
        python - "$LATEST_CSV" <<PY > "$CHECKSUM_PATH"
import hashlib
import sys
h=hashlib.sha256()
with open(sys.argv[1],'rb') as f:
    for b in iter(lambda: f.read(8192), b''):
        h.update(b)
print(h.hexdigest())
PY
      fi
    fi
    # if SUMMARY lacks snapshot path, inject it into fallback JSON
    if ! echo "$SUMMARY" | grep -q '"snapshot"' || echo "$SUMMARY" | grep -q '"snapshot":null'; then
      # produce minimal JSON summary including snapshot path
      if command -v jq >/dev/null 2>&1; then
        SUMMARY=$(jq -n --arg j "$JOB_ID" --arg s "$LATEST_CSV" '{job_id:$j,status:"success",snapshot:$s}' 2>/dev/null)
      elif command -v python >/dev/null 2>&1; then
        SUMMARY=$(python -c "import json,sys; print(json.dumps({'job_id':sys.argv[1],'status':'success','snapshot':sys.argv[2]}))" "$JOB_ID" "$LATEST_CSV")
      else
        job_id_escaped=$(json_escape "$JOB_ID")
        latest_csv_escaped=$(json_escape "$LATEST_CSV")
        SUMMARY="{\"job_id\":\"$job_id_escaped\",\"status\":\"success\",\"snapshot\":\"$latest_csv_escaped\"}"
      fi
    fi
  fi
fi

# Emit final summary to stdout and the log.
echo "$SUMMARY"
echo "$SUMMARY" >> "$LOGFILE"
exit 0

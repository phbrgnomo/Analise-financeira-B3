#!/usr/bin/env bash
# Example quickstart runner (CI-friendly skeleton)
set -euo pipefail

# Defaults
DATA_DIR=${DATA_DIR:-./dados}
SNAPSHOT_DIR=${SNAPSHOT_DIR:-./snapshots}
OUTPUTS_DIR=${OUTPUTS_DIR:-./outputs}
LOG_DIR=${LOG_DIR:-./logs}
TICKER="PETR4.SA"
FORMAT="json"
NO_NETWORK=0

usage(){
  echo "Usage: $0 [--no-network] [--ticker TICKER] [--format json|text]"
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-network) NO_NETWORK=1; shift ;;
    --ticker) TICKER="$2"; shift 2 ;;
    --format) FORMAT="$2"; shift 2 ;;
    --help|-h) usage ;;
    *) echo "Unknown arg: $1"; usage ;;
  esac
done

mkdir -p "$SNAPSHOT_DIR" "$OUTPUTS_DIR" "$LOG_DIR"

JOB_ID=$(uuidgen 2>/dev/null || date +%s)
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
SNAPFILE="$SNAPSHOT_DIR/${TICKER//./_}-$TIMESTAMP.csv"
LOGFILE="$LOG_DIR/run_quickstart_${TIMESTAMP}.log"

echo "job_id=$JOB_ID ticker=$TICKER no_network=$NO_NETWORK" > "$LOGFILE"

echo "Running quickstart example for $TICKER (no_network=$NO_NETWORK)..." >> "$LOGFILE"

if [[ $NO_NETWORK -eq 1 ]]; then
  # Use fixtures: call project CLI with flags to use sample tickers
  poetry run main --no-network --ticker "$TICKER" --format "$FORMAT" --sample-tickers tests/fixtures/sample_ticker.csv > "$OUTPUTS_DIR/quickstart_${TIMESTAMP}.out" 2>>"$LOGFILE" || EXIT_CODE=$?
else
  poetry run main --ticker "$TICKER" --format "$FORMAT" > "$OUTPUTS_DIR/quickstart_${TIMESTAMP}.out" 2>>"$LOGFILE" || EXIT_CODE=$?
fi

EXIT_CODE=${EXIT_CODE:-0}

if [[ $EXIT_CODE -ne 0 ]]; then
  echo "{\"job_id\":\"$JOB_ID\",\"status\":\"failure\"}" >> "$LOGFILE"
  echo "Script failed; see $LOGFILE"
  exit $EXIT_CODE
fi

# On success, record a simple JSON summary to stdout and log
SUMMARY=$(jq -n --arg job_id "$JOB_ID" --arg status "success" --arg snapshot "$SNAPFILE" --argjson elapsed_sec 1 '{job_id:$job_id,status:$status,elapsed_sec:$elapsed_sec,snapshot:$snapshot}')
if [[ "$FORMAT" == "json" ]]; then
  echo "$SUMMARY"
else
  echo "Quickstart completed: $JOB_ID -> $SNAPFILE"
fi

echo "$SUMMARY" >> "$LOGFILE"
exit 0

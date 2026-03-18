# Sprint Report: Story 3.1 - Quickstart CLI end‑to‑end

## Summary

Implemented an end-to-end quickstart CLI command `poetry run main --ticker <TICKER>` that:

- Executes ingest → persist → snapshot pipeline (using adapters + canonical mapper)
- Produces a deterministic snapshot CSV under `snapshots/` named `<TICKER>-YYYYMMDD.csv`
- Writes companion `.checksum` file and records metadata in the metadata DB
- Prints a concise summary with `job_id`, `duration_sec`, `snapshot path`, `rows` and per-ticker details
- Supports JSON output for CI consumption
- Adds operational flags: `--dry-run`, `--no-network`, `--sample-tickers`, `--max-days`, `--force-refresh`
- Adds optional `--run-notebook` to execute the analysis notebook via `papermill` (when installed)

## Tests Added / Updated

- Added an integration test `tests/integration/test_quickstart_cli_no_network.py` that runs the CLI in `--no-network` mode, validates JSON summary output, and confirms snapshot + `.checksum` are generated and match.

- Extended `tests/test_cli.py` to validate:
  - `--sample-tickers` overrides default tickers
  - `--max-days` correctly passes start/end into ingest
  - `--run-notebook` calls `papermill.execute_notebook` when available
  - JSON output includes `job_id` and snapshot metadata

- Adjusted snapshot filename handling and retention tests to match new date-only pattern.

## Notes

- Snapshot retention still functions: the filename is based on the snapshot creation date. In tests, the `mock_time_progression` fixture now advances by one day so successive ingests produce distinct files.

- `papermill` is optional; if missing, `--run-notebook` exits with code 2 and prints an actionable message.

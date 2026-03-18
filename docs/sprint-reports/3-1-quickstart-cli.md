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

## Example

Run the quickstart command for a real ticker (e.g., `PETR4`):

```sh
poetry run main --ticker PETR4
```

Example plain-text output (actual values such as `job_id`, `duration_sec`, `snapshot` path and `rows` may vary):

```
job_id=0d4f5a7e-xxxx-xxxx-xxxx-xxxxxxxxxxxx | duration_sec=2.34 | sucesso=1 falhas=0
ticker=PETR4 snapshot=snapshots/PETR4-20260318.csv rows=123
```

You can also output machine-readable JSON for CI consumers:

```sh
poetry run main --ticker PETR4 --format json
```

Example JSON output:

```json
{
  "status": "success",
  "job_id": "0d4f5a7e-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "duration_sec": 2.34,
  "tickers": [
    {
      "ticker": "PETR4",
      "provider": "yfinance",
      "status": "success",
      "rows_ingested": 123,
      "rows_returns": 123,
      "snapshot_path": "snapshots/PETR4-20260318.csv",
      "snapshot_checksum": "<sha256-hash>",
      "error_message": null
    }
  ]
}
```

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

## Limitations

- **No data for a ticker**: If the provider returns an empty dataset for a ticker, the pipeline reports a warning and does **not** write a snapshot file (or update the snapshot cache). The CLI will still run through the loop, but the ticker will show up as a warning/failed step.

- **Snapshot overwrite behavior**: Snapshots are named using the current date (YYYYMMDD), so rerunning the command for the same ticker on the same day will overwrite the existing snapshot CSV/`.checksum` pair. The snapshot retention logic (`keep_latest`) may also prune older snapshots automatically.

- **Network/offline mode & `--run-notebook`**: `--no-network` makes the CLI use the dummy provider (no external requests), but it does **not** affect notebook execution. Running `--run-notebook` still requires `papermill` to be installed; if missing, the command exits with code 2 and prints a message.

- **`--max-days` range handling**: The `--max-days` flag is converted into a `start/end` date window using `_resolve_sample_window`, which enforces a minimum of 1 day (negative or zero values are treated as 1). The end date is always the current UTC date.

- **Concurrent execution**: Ingestion is serialized per ticker via a filesystem lock (configurable via `LOCK_DIR`). Concurrent runs for the same ticker will block (or fail with a `LockTimeout` when using non-blocking mode). Other tickers can run in parallel without interference.

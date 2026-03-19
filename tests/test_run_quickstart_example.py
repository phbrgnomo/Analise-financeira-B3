import json
import os
import subprocess
from pathlib import Path


def test_run_quickstart_example_creates_snapshot_and_log(tmp_path: Path) -> None:
    """Smoke test: run the example script and verify it produces artifacts."""

    repo_root = Path(__file__).resolve().parents[1]
    outputs_dir = tmp_path / "outputs"
    snapshots_dir = tmp_path / "snapshots"
    logs_dir = tmp_path / "logs"
    dados_dir = tmp_path / "dados"

    env = os.environ.copy()
    env.update(
        {
            "OUTPUTS_DIR": str(outputs_dir),
            "SNAPSHOT_DIR": str(snapshots_dir),
            "LOG_DIR": str(logs_dir),
            "DATA_DIR": str(dados_dir),
        }
    )

    proc = subprocess.run(
        [
            str(repo_root / "examples" / "run_quickstart_example.sh"),
            "--no-network",
            "--format",
            "json",
        ],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert proc.returncode == 0, f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"

    # Ensure the script prints a JSON summary
    summary = json.loads(proc.stdout)
    assert summary.get("status") == "success"
    assert "job_id" in summary

    log_files = list(logs_dir.glob("run_quickstart_*.log"))
    assert log_files, f"No log file created in {logs_dir}"
    log_text = log_files[0].read_text(encoding="utf-8")
    assert "job_id" in log_text
    assert "status" in log_text

    # Ensure snapshot + checksum exist in the snapshot dir
    snapshots = list(snapshots_dir.glob("*PETR4*"))
    assert snapshots, f"No snapshot created in {snapshots_dir}"

    csv_files = [p for p in snapshots if p.suffix == ".csv"]
    assert csv_files, "Expected a CSV snapshot file"

    checksum_files = [p for p in snapshots if p.suffix == ".checksum"]
    assert checksum_files, "Expected a .checksum file alongside snapshot"

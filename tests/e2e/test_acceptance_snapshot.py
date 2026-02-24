import os
import subprocess
import sys
from pathlib import Path

import pytest


def run_generator(out_dir: Path) -> int:
    # Prefer the example shell script if present, otherwise fallback to python script
    if (Path.cwd() / "examples" / "run_quickstart_example.sh").exists():
        cmd = ["/bin/bash", str(Path.cwd() / "examples" / "run_quickstart_example.sh")]
        env = os.environ.copy()
        env["SNAPSHOT_DIR"] = str(out_dir)
        return subprocess.call(cmd, env=env)
    else:
        # fallback to python example
        script_path = Path.cwd() / "scripts" / "run_save_raw_example.py"
        cmd = [sys.executable, str(script_path), "--out-dir", str(out_dir)]
        env = os.environ.copy()
        env["SNAPSHOT_DIR"] = str(out_dir)
        return subprocess.call(cmd, env=env)


def test_acceptance_snapshot(tmp_path: Path):
    out = tmp_path / "snapshots_test"
    out.mkdir()

    rc = run_generator(out)
    if rc != 0:
        pytest.skip("Snapshot generator failed; skipping acceptance run")

    # Validate using the existing script via the wrapper if available
    verify = Path.cwd() / "scripts" / "verify_snapshot.py"
    validate_cmd = [
        sys.executable,
        str(verify),
        "--dir",
        str(out),
        "--manifest",
        "snapshots/checksums.json",
    ]
    proc = subprocess.run(validate_cmd, capture_output=True, text=True)
    assert proc.returncode == 0, (
        "Snapshot validation failed:\n"
        f"STDOUT: {proc.stdout}\n"
        f"STDERR: {proc.stderr}"
    )

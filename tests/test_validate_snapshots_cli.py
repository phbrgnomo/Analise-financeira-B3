import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from src.utils.checksums import serialize_df_bytes, sha256_bytes


def _write_csv(path: Path) -> None:
    data = serialize_df_bytes(
        pd.DataFrame({"Date": ["2020-01-01"], "Close": [10.0]}),
        index=False,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.with_suffix(path.suffix + ".checksum").write_text(sha256_bytes(data))


def test_update_writes_manifest(tmp_path: Path):
    cur_dir = tmp_path / "cur"
    cur_dir.mkdir()
    f = cur_dir / "SAMPLE.csv"
    _write_csv(f)

    manifest = tmp_path / "out_manifest.json"

    cmd = [
        sys.executable,
        "scripts/validate_snapshots.py",
        "--dir",
        str(cur_dir),
        "--manifest",
        str(manifest),
        "--update",
        "--allow-external",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert manifest.exists()
    data = json.loads(manifest.read_text())
    assert "files" in data and isinstance(data["files"], dict)


def test_allow_external_remap_collision(tmp_path: Path):
    # create two files with same basename under different subdirs
    d = tmp_path / "d"
    p1 = d / "a" / "same.csv"
    p2 = d / "b" / "same.csv"
    _write_csv(p1)
    _write_csv(p2)

    manifest = tmp_path / "m.json"

    cmd = [
        sys.executable,
        "scripts/validate_snapshots.py",
        "--dir",
        str(d),
        "--manifest",
        str(manifest),
        "--allow-external",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    # collision should cause exit code 3 (SystemExit(3))
    assert proc.returncode == 3


def test_invalid_manifest_path_errors(tmp_path: Path):
    # calling with manifest outside snapshots without --allow-external should fail
    d = tmp_path / "d"
    d.mkdir()
    p = d / "ok.csv"
    _write_csv(p)

    manifest = tmp_path / "out" / "m.json"

    cmd = [
        sys.executable,
        "scripts/validate_snapshots.py",
        "--dir",
        str(d),
        "--manifest",
        str(manifest),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 2

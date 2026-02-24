import subprocess
import sys
from pathlib import Path

import pandas as pd

from src.utils.checksums import serialize_df_bytes, sha256_bytes


def _make_csv_bytes() -> bytes:
    """Cria um DataFrame pequeno determinístico e retorna bytes CSV.

    O CSV é serializado de forma determinística para uso em testes E2E.
    """
    # dataframe pequeno determinístico
    df = pd.DataFrame({"Date": ["2020-01-01", "2020-01-02"], "Close": [10.0, 11.5]})
    return serialize_df_bytes(
        df,
        index=False,
        date_format="%Y-%m-%dT%H:%M:%S",
        float_format="%.10g",
    )


def test_acceptance_snapshot(tmp_path: Path):
    # Create a deterministic snapshots dir with files that will be remapped
    out = tmp_path / "snapshots_test"
    out.mkdir()

    # Create a single snapshot file matching the repository manifest basename
    name = "PETR4_snapshot.csv"
    fp = out / name
    data = _make_csv_bytes()
    fp.write_bytes(data)

    # write checksum file that mirrors how pipeline writes it
    chk = fp.with_suffix(fp.suffix + ".checksum")
    chk.write_text(sha256_bytes(data))

    # First generate a manifest for this tmp dir, then validate against it
    tmp_manifest = tmp_path / "manifest.json"
    gen_cmd = [
        sys.executable,
        "scripts/validate_snapshots.py",
        "--dir",
        str(out),
        "--manifest",
        str(tmp_manifest),
        "--update",
        "--allow-external",
    ]
    gen = subprocess.run(gen_cmd, capture_output=True, text=True)
    assert gen.returncode == 0, (
        f"Manifest generation failed: {gen.stderr}\n{gen.stdout}"
    )

    # Call the wrapper which forwards to scripts/validate_snapshots.py
    verify = Path.cwd() / "scripts" / "verify_snapshot.py"
    validate_cmd = [
        sys.executable,
        str(verify),
        "--dir",
        str(out),
        "--manifest",
        str(tmp_manifest),
        "--allow-external",
    ]
    proc = subprocess.run(validate_cmd, capture_output=True, text=True)
    assert proc.returncode == 0, (
        "Snapshot validation failed:\n"
        f"STDOUT: {proc.stdout}\n"
        f"STDERR: {proc.stderr}"
    )

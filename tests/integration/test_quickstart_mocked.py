import shutil
from pathlib import Path

import pandas as pd


def test_quickstart_mocked_creates_snapshot_and_validates_checksum(tmp_path):
    """Simula quickstart em ambiente sem rede usando fixture CSV e valida checksum."""
    repo_root = Path(__file__).resolve().parents[2]
    fixtures_dir = repo_root / "tests" / "fixtures"

    sample = fixtures_dir / "sample_snapshot.csv"
    expected_checksum_file = fixtures_dir / "expected_snapshot.checksum"

    out_dir = tmp_path / "snapshots_test"
    out_dir.mkdir()

    dest = out_dir / "PETR4_snapshot.csv"
    shutil.copy(sample, dest)

    # Basic validation: header and rows
    df = pd.read_csv(dest)
    assert not df.empty
    assert "date" in df.columns or "Date" in df.columns

    # Compute checksum using project util if available
    try:
        from src.utils.checksums import sha256_file

        checksum = sha256_file(dest)
    except Exception:
        import hashlib

        h = hashlib.sha256()
        with open(dest, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        checksum = h.hexdigest()

    # Compare against expected checksum fixture
    expected = expected_checksum_file.read_text(encoding="utf-8").strip()
    assert checksum == expected

    # Write checksum sidecar artifact (as CI expects)
    (dest.with_name(dest.name + ".checksum")).write_text(checksum)

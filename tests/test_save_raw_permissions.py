import os
import platform
import stat
from pathlib import Path

import pandas as pd
import pytest

from src.ingest.pipeline import save_raw_csv


@pytest.mark.skipif(platform.system() == "Windows", reason="POSIX permissions only")
def test_save_raw_csv_set_permissions(tmp_path):
    df = pd.DataFrame({"col1": [1], "col2": [2]})

    raw_root = tmp_path / "raw"
    metadata_path = tmp_path / "metadata" / "ingest_logs.json"
    ts = "20260220T000000Z"

    meta = save_raw_csv(
        df,
        "testprov",
        "TICK",
        ts,
        raw_root=raw_root,
        metadata_path=metadata_path,
        set_permissions=True,
    )

    csv_path = Path(meta["filepath"])
    assert csv_path.exists()

    # check permissions are owner read/write only (0o600)
    mode = stat.S_IMODE(os.stat(csv_path).st_mode)
    assert mode == 0o600

    checksum_path = Path(f"{str(csv_path)}.checksum")
    assert checksum_path.exists()
    mode_checksum = stat.S_IMODE(os.stat(checksum_path).st_mode)
    assert mode_checksum == 0o600


import pandas as pd

from src.etl.mapper import to_canonical
from src.ingest.pipeline import save_raw_csv
from src.utils.checksums import serialize_df_bytes, sha256_bytes


def test_end_to_end_checksum_agreement(tmp_path):
    # Arrange
    df = pd.DataFrame(
        {
            "Open": [10.0, 11.0],
            "High": [12.0, 13.0],
            "Low": [9.0, 10.0],
            "Close": [11.0, 12.0],
            "Adj Close": [10.5, 11.5],
            "Volume": [100, 200],
        },
        index=pd.date_range("2026-02-01", periods=2, freq="D"),
    )

    raw_root = tmp_path / "raw"
    metadata_path = tmp_path / "metadata" / "ingest_logs.json"

    # Act: save raw
    meta = save_raw_csv(
        df,
        "testprov",
        "TICK",
        raw_root=raw_root,
        metadata_path=metadata_path,
    )

    assert meta["status"] == "success"

    # Map to canonical reusing checksum and fetched_at
    canonical = to_canonical(
        df,
        provider_name="testprov",
        ticker="TICK",
        raw_checksum=meta["raw_checksum"],
        fetched_at=meta["fetched_at"],
    )

    # Verify agreement
    assert canonical.attrs["raw_checksum"] == meta["raw_checksum"]
    # Also verify checksum corresponds to serialized bytes of df
    df_bytes = serialize_df_bytes(
        df.sort_index(),
        index=True,
        date_format="%Y-%m-%dT%H:%M:%S",
        float_format="%.10g",
        na_rep="",
    )
    assert sha256_bytes(df_bytes) == meta["raw_checksum"]

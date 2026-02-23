import pandas as pd

from src import db, validation
from src.etl.mapper import to_canonical
from src.validation import ValidationError


def make_good_df():
    return pd.DataFrame(
        [
            {
                "date": "2021-06-01",
                "open": 40.0,
                "high": 41.0,
                "low": 39.5,
                "close": 40.5,
                "volume": 400,
                "source": "e",
                "fetched_at": "2021-06-01T12:00:00Z",
            },
            {
                "date": "2021-06-02",
                "open": 41.0,
                "high": 42.0,
                "low": 40.5,
                "close": 41.5,
                "volume": 410,
                "source": "e",
                "fetched_at": "2021-06-02T12:00:00Z",
            },
        ]
    )


def make_bad_df():
    # many invalid rows to trigger threshold
    return pd.DataFrame({"date": ["bad"] * 10, "open": ["x"] * 10})


def test_e2e_validate_write_read_success(tmp_path):
    db_file = tmp_path / "dados" / "data.db"
    db.create_tables_if_not_exists(db_path=str(db_file))

    raw_df = make_good_df()
    # map provider DF to canonical schema first
    canonical = to_canonical(raw_df, provider_name="e", ticker="TSTE2E")

    # validate (threshold high so it won't abort)
    valid_df, invalid_df, summary, details = validation.validate_and_handle(
        canonical,
        provider="e",
        ticker="TSTE2E",
        raw_file="raw.csv",
        ts="20210601",
        raw_root=str(tmp_path),
        metadata_path=str(tmp_path / "metadata.json"),
        threshold=1.0,
        abort_on_exceed=False,
        persist_invalid=False,
        db_path=str(db_file),
    )

    assert not valid_df.empty
    # write validated rows
    db.write_prices(valid_df, "TSTE2E", db_path=str(db_file))

    # read back and assert count
    out = db.read_prices("TSTE2E", db_path=str(db_file))
    assert len(out) == len(valid_df)


def test_e2e_validate_write_read_abort_on_threshold(tmp_path):
    db_file = tmp_path / "dados" / "data.db"
    db.create_tables_if_not_exists(db_path=str(db_file))

    # create a canonical-like DataFrame with invalid values to exceed threshold
    bad = pd.DataFrame(
        {
            "ticker": ["TSTE2E"] * 5,
            "date": ["bad-date"] * 5,
            "open": ["x"] * 5,
            "high": [None] * 5,
            "low": [None] * 5,
            "close": [None] * 5,
            "volume": [None] * 5,
            "source": ["e"] * 5,
            "fetched_at": ["bad-time"] * 5,
            "raw_checksum": ["abc"] * 5,
        }
    )

    # use strict threshold so validation aborts
    try:
        validation.validate_and_handle(
            bad,
            provider="e",
            ticker="TSTE2E",
            raw_file="raw.csv",
            ts="20210601",
            raw_root=str(tmp_path),
            metadata_path=str(tmp_path / "metadata.json"),
            threshold=0.01,
            abort_on_exceed=True,
            persist_invalid=False,
            db_path=str(db_file),
        )
        raised = False
    except ValidationError:
        raised = True

    assert raised

    # ensure nothing was written
    out = db.read_prices("TSTE2E", db_path=str(db_file))
    assert out.empty

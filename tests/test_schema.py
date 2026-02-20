import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_schema():
    root = _project_root()
    schema_path = root / "docs" / "schema.json"
    return json.loads(schema_path.read_text())


def _schema_columns():
    schema = _load_schema()
    cols = []
    for col in schema.get("columns", []):
        if isinstance(col, dict) and "name" in col:
            cols.append(col["name"])
        else:
            cols.append(col)
    return cols


def test_example_matches_schema_header():
    root = _project_root()
    example_path = root / "dados" / "samples" / "ticker_example.csv"
    expected = _schema_columns()
    with example_path.open(newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
    assert header == expected


def test_to_canonical_from_yfinance_df(tmp_path):
    from src.dados_b3 import to_canonical  # type: ignore[import]

    raw_csv_path = tmp_path / "raw_yahoo.csv"
    rows = [
        ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"],
        ["2024-01-02", "10.0", "11.0", "9.5", "10.5", "10.5", "1000"],
        ["2024-01-03", "10.5", "11.5", "10.0", "11.0", "11.0", "1500"],
    ]
    with raw_csv_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    df = pd.read_csv(raw_csv_path, parse_dates=["Date"]).set_index("Date")

    fetched_at_dt = datetime(2024, 1, 4, 12, 34, 56, tzinfo=timezone.utc)

    canonical_df = to_canonical(
        df=df, raw_csv_path=raw_csv_path, fetched_at=fetched_at_dt, ticker="TEST4.SA"
    )

    expected_columns = _schema_columns()
    assert list(canonical_df.columns) == expected_columns

    date_strings = [str(d) for d in canonical_df["date"].tolist()]
    assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) for s in date_strings)

    assert "fetched_at" in canonical_df.columns
    for v in canonical_df["fetched_at"].astype(str).tolist():
        assert v.endswith("Z")
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z", v)

    expected_checksum = hashlib.sha256(raw_csv_path.read_bytes()).hexdigest()
    assert "raw_checksum" in canonical_df.columns
    assert canonical_df["raw_checksum"].nunique() == 1
    assert canonical_df["raw_checksum"].iloc[0] == expected_checksum


def test_fetch_yahoo_resets_index_and_columns(monkeypatch):
    from src import dados_b3  # type: ignore[import]

    captured = {}

    def fake_download(tickers, start=None, end=None, interval="1d", **kwargs):
        captured["tickers"] = tickers
        captured["start"] = start
        captured["end"] = end
        captured["interval"] = interval
        idx = pd.date_range("2024-01-02", periods=2, freq="D")
        return pd.DataFrame(
            {
                "Open": [10.0, 10.5],
                "High": [11.0, 11.5],
                "Low": [9.5, 10.0],
                "Close": [10.5, 11.0],
                "Adj Close": [10.5, 11.0],
                "Volume": [1000, 1500],
            },
            index=idx,
        )

    monkeypatch.setattr(
        dados_b3, "yf", type("YFModule", (), {"download": fake_download})
    )
    df = dados_b3.fetch_yahoo("TEST4.SA", start="2024-01-01", end="2024-01-31")

    assert captured["tickers"] == "TEST4.SA"
    assert captured["interval"] == "1d"
    assert isinstance(df.index, pd.RangeIndex)
    for col in ["Open", "High", "Low", "Close", "Adj Close", "Volume"]:
        assert col in df.columns


def test_cotacao_indice_dia_uses_hat_prefix(monkeypatch):
    from src import dados_b3  # type: ignore[import]

    called = []

    def fake_download(tickers, *args, **kwargs):
        called.append(tickers)
        idx = pd.date_range("2024-01-02", periods=1, freq="D")
        return pd.DataFrame(
            {
                "Open": [10.0],
                "High": [11.0],
                "Low": [9.5],
                "Close": [10.5],
                "Adj Close": [10.5],
                "Volume": [1000],
            },
            index=idx,
        )

    monkeypatch.setattr(
        dados_b3, "yf", type("YFModule", (), {"download": fake_download})
    )
    dados_b3.cotacao_indice_dia("IBOV")
    assert len(called) == 1
    assert called[0] == "^IBOV"


def test_cotacao_ativo_dia_uses_b3_suffix(monkeypatch):
    from src import dados_b3  # type: ignore[import]

    called = []

    def fake_download(tickers, *args, **kwargs):
        called.append(tickers)
        idx = pd.date_range("2024-01-02", periods=1, freq="D")
        return pd.DataFrame(
            {
                "Open": [10.0],
                "High": [11.0],
                "Low": [9.5],
                "Close": [10.5],
                "Adj Close": [10.5],
                "Volume": [1000],
            },
            index=idx,
        )

    monkeypatch.setattr(
        dados_b3, "yf", type("YFModule", (), {"download": fake_download})
    )
    dados_b3.cotacao_ativo_dia("PETR4")
    assert len(called) == 1
    assert called[0] == "PETR4.SA"
def test_example_matches_schema():
    root = Path(__file__).resolve().parent.parent
    schema_path = root / "docs" / "schema.json"
    example_path = root / "dados" / "samples" / "ticker_example.csv"

    schema = json.loads(schema_path.read_text())
    assert schema.get("schema_version") == 1
    columns = [c["name"] for c in schema["columns"]]

    with example_path.open() as f:
        reader = csv.DictReader(f)
        # Ensure header matches schema column order
        assert reader.fieldnames == columns
        rows = list(reader)

    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    iso_re = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    hex_re = re.compile(r"^[0-9a-f]{64}$")

    for r in rows:
        if not date_re.match(r["date"]):
            raise AssertionError(f"date invalid: {r['date']}")
        if not iso_re.match(r["fetched_at"]):
            raise AssertionError(f"fetched_at invalid: {r['fetched_at']}")
        if not hex_re.match(r["raw_checksum"]):
            raise AssertionError(f"raw_checksum invalid: {r['raw_checksum']}")

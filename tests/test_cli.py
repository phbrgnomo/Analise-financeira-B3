import subprocess
import sys

from typer.testing import CliRunner

from src.main import app


def test_cli_help():
    """The `test_cli_help` function verifies the CLI help output.

    Ensures that invoking `--help` for the `app` displays the expected options.
    """
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # rich help output varies across Typer/Click versions; just ensure the
    # usage line is present rather than hard-coding the "Options" label.
    assert "Usage:" in result.output

def test_ingest_snapshot_help():
    runner = CliRunner()
    result = runner.invoke(app, ["ingest-snapshot", "--help"])
    assert result.exit_code == 0, (
        f"CLI help falhou (exit_code={result.exit_code}): "
        f"{result.exception}"
    )
    assert "ingest-snapshot" in result.output
    # verify that the new flags appear
    assert "--force-refresh" in result.output
    assert "--ttl" in result.output
    assert "--cache-file" in result.output


def test_main_help_exit_code_and_output():
    """Invoca `python -m src.main --help` e verifica saída e código de retorno."""
    completed = subprocess.run(
        [sys.executable, "-m", "src.main", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0
    assert "usage" in completed.stdout.lower() or "usage" in completed.stderr.lower()
    # O fluxo principal agora é o subcomando `run`
    completed2 = subprocess.run(
        [sys.executable, "-m", "src.main", "run", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed2.returncode == 0
    assert "--ticker" in completed2.stdout
    assert "--provider" in completed2.stdout
    # Help may emit deprecation warnings to stderr in some environments.
    # Ignore stderr content in the assertions.


def test_run_uses_ingest_pipeline(monkeypatch):
    from src.main import app

    calls = []

    def fake_ingest(ticker, source="yfinance", dry_run=False, force_refresh=False):
        calls.append(
            {
                "ticker": ticker,
                "source": source,
                "dry_run": dry_run,
                "force_refresh": force_refresh,
            }
        )
        return {"status": "success"}

    monkeypatch.setattr("src.ingest.pipeline.ingest", fake_ingest)

    calls_to_compute = []

    def fake_compute(ticker: str, *args, **kwargs):
        calls_to_compute.append(ticker)
        # mimic structure returned by helper
        return {"rows": 1, "persisted": True, "sample_df": None}

    monkeypatch.setattr("src.main._compute_returns_for_ticker", fake_compute)

    runner = CliRunner()
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    assert calls, "esperávamos que ingest fosse chamado"
    assert calls[0]["ticker"] == "PETR4"
    assert calls[0]["source"] == "yfinance"

    # e também precisamos que ao menos um ticker seja enviado ao cálculo de
    # retornos
    assert calls_to_compute, "_compute_returns_for_ticker não foi invocado"

    # compute_returns deve ser chamado para cada ticker que passou pelo
    # pipeline de ingest.  O comportamento padrão do comando `run` é iterar
    # sobre DEFAULT_TICKERS (PETR4, ITUB3, BBDC4), mas o teste não precisa
    # conhecer essa lista explicitamente; basta comparar contra as chamadas
    # de ingest gravadas.
    ingest_tickers = [c["ticker"] for c in calls]
    # todos os tickers calculados devem aparecer na lista de ingest
    # usamos conjuntos normalizados para evitar loops explícitos
    norm_ingest = {t.rstrip(".SA") for t in ingest_tickers}
    norm_compute = {t.rstrip(".SA") for t in calls_to_compute}
    assert norm_compute.issubset(norm_ingest), (
        f"ticker inesperado para cálculo de retornos: "
        f"{norm_compute - norm_ingest}"
    )
    # e não deve haver chamadas extras
    assert len(calls_to_compute) == len(ingest_tickers)


# ---------------------------------------------------------------------------
# missing-command tests added per review
# ---------------------------------------------------------------------------

def test_compute_returns_single_ticker(monkeypatch):
    """`compute-returns` invoca o helper e imprime linhas geradas."""
    from src.main import app

    called: list[tuple] = []

    def fake_compute(ticker, start, end, dry_run):
        called.append((ticker, start, end, dry_run))
        return {"rows": 3, "persisted": True, "sample_df": None}

    monkeypatch.setattr("src.main._compute_returns_for_ticker", fake_compute)
    # ensure no DB dependency when listing all tickers
    monkeypatch.setattr("src.db.list_price_tickers", lambda: ["PETR4"])

    runner = CliRunner()
    result = runner.invoke(app, ["compute-returns", "--ticker", "PETR4"])
    assert result.exit_code == 0
    assert "retornos" in result.output
    assert called == [("PETR4", None, None, False)]


def test_compute_returns_date_range(monkeypatch):
    """Passing ``--start`` and ``--end`` should reach helper with values."""
    from src.main import app

    called = []

    def fake_compute(ticker, start, end, dry_run):
        called.append((ticker, start, end, dry_run))
        return {"rows": 1, "persisted": True, "sample_df": None}

    monkeypatch.setattr("src.main._compute_returns_for_ticker", fake_compute)
    # provide a ticker so we exercise the loop
    monkeypatch.setattr("src.db.list_price_tickers", lambda: ["PETR4"])
    monkeypatch.setattr("src.db.resolve_existing_ticker", lambda t: t)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "compute-returns",
            "--start",
            "2020-01-01",
            "--end",
            "2020-01-31",
        ],
    )
    assert result.exit_code == 0
    assert called == [("PETR4", "2020-01-01", "2020-01-31", False)]


def test_compute_returns_all_when_empty(monkeypatch):
    """Se não há tickers no banco, CLI imprime aviso e retorna 0."""
    from src.main import app

    monkeypatch.setattr("src.db.list_price_tickers", lambda: [])

    runner = CliRunner()
    result = runner.invoke(app, ["compute-returns"])
    assert result.exit_code == 0
    assert "Nenhum ticker encontrado" in result.output


def test_export_csv_success(tmp_path, monkeypatch):
    """`export-csv` escreve arquivo quando ticker existe."""
    import pandas as pd

    from src.main import app

    # resolve returns normalized but we don't care about output option
    monkeypatch.setattr("src.db.resolve_existing_ticker", lambda t: t)
    monkeypatch.setattr(
        "src.db.read_prices",
        lambda t, start=None, end=None: pd.DataFrame(
            {"date": ["2021-01-01"], "price": [1]}
        ),
    )
    # intercept default DATA_DIR in main module so file lands in tmp_path
    import src.main as mainmod
    monkeypatch.setattr(mainmod, "DATA_DIR", tmp_path)

    runner = CliRunner()
    result = runner.invoke(app, ["export-csv", "--ticker", "PETR4"])
    assert result.exit_code == 0
    out = tmp_path / "PETR4.csv"
    assert out.exists(), "arquivo de saída deveria ser criado"
    assert "linha" in result.output


def test_export_csv_not_found(monkeypatch):
    """CLI falha se o ticker válido não estiver no banco nem na variante."""
    from src.main import app
    # use a valid ticker so normalization passes
    monkeypatch.setattr("src.db.resolve_existing_ticker", lambda t: None)
    monkeypatch.setattr("src.tickers.ticker_variants", lambda t: (t, f"{t}.SA"))

    runner = CliRunner()
    result = runner.invoke(app, ["export-csv", "--ticker", "PETR4"])
    assert result.exit_code != 0
    assert "não encontrado" in result.stderr.lower()


def test_ingest_snapshot_command(monkeypatch, tmp_path):
    """Invocar `ingest-snapshot` dispara ingest_snapshot() com argumentos."""
    from src.main import app

    called = []

    def fake_snapshot(path, ticker, force_refresh=False, ttl=None, cache_file=None):
        called.append((path, ticker, force_refresh, ttl, cache_file))
        return {"status": "ok"}

    monkeypatch.setattr("src.ingest_cli.ingest_snapshot", fake_snapshot)

    snapshot = tmp_path / "foo.csv"
    snapshot.write_text("date,close\n2021-01-01,1")

    runner = CliRunner()
    # snapshot path is a required positional argument and must come first
    result = runner.invoke(
        app,
        [
            "ingest-snapshot",
            str(snapshot),
            "--ticker",
            "PETR4",
            "--force-refresh",
            "--ttl",
            "123",
            "--cache-file",
            "foo.json",
        ],
    )
    assert result.exit_code == 0
    assert called and called[0][0] == str(snapshot)
    assert called[0][1] == "PETR4"
    assert called[0][2] is True
    # TTL and cache args should also be passed through
    # CLI provides numeric ttl which is converted to float
    assert called[0][3] == 123.0
    assert called[0][4] == "foo.json"
    assert "Ingestão de snapshot concluída" in result.output

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.main import app


def _strip_ansi(s: str) -> str:
    """Remove sequências ANSI/escape para tornar asserções independentes
    do formatter.
    """
    ansi = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
    return ansi.sub("", s)


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
    """Verifica que a ajuda do subcomando `snapshots ingest` inclui novos
    flags como --force-refresh, --ttl e --cache-file e retorna exit code 0.
    """
    runner = CliRunner()
    result = runner.invoke(app, ["snapshots", "ingest", "--help"])
    assert result.exit_code == 0, (
        f"CLI help falhou (exit_code={result.exit_code}): {result.exception}"
    )
    plain = _strip_ansi(result.output)
    # verify that the new flags appear
    assert "--force-refresh" in plain
    assert "--ttl" in plain
    assert "--cache-file" in plain


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
    plain2 = _strip_ansi(completed2.stdout)
    assert "--ticker" in plain2
    assert "--provider" in plain2
    # Help may emit deprecation warnings to stderr in some environments.
    # Ignore stderr content in the assertions.


def test_run_uses_ingest_pipeline(monkeypatch):
    """Verifica que o comando `run` da CLI invoca o pipeline de ingest e
    prossegue para o cálculo de retornos.

    O teste substitui as funções reais por **mocks** que registram as
    chamadas, permitindo asserts sobre ticker, fonte e fluxo geral.
    """

    calls = []

    def fake_ingest(
        ticker,
        source="yfinance",
        dry_run=False,
        force_refresh=False,
        **kwargs,
    ):
        calls.append(
            {
                "ticker": ticker,
                "source": source,
                "dry_run": dry_run,
                "force_refresh": force_refresh,
                **kwargs,
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
    # Ensure the summary includes a job_id and per-ticker snapshot info.
    assert "job_id=" in result.output
    assert "snapshot=" in result.output
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
        f"ticker inesperado para cálculo de retornos: {norm_compute - norm_ingest}"
    )
    # e não deve haver chamadas extras
    assert len(calls_to_compute) == len(ingest_tickers)


def test_compute_returns_single_ticker(monkeypatch):
    """`compute-returns` invoca o helper e imprime linhas geradas."""
    from src.main import app

    called: list[tuple] = []

    def fake_compute(ticker, start, end, dry_run):
        called.append((ticker, start, end, dry_run))
        return {"rows": 3, "persisted": True, "sample_df": None}

    monkeypatch.setattr("src.main._compute_returns_for_ticker", fake_compute)
    # ensure no DB calls during command (neither list nor resolve)
    monkeypatch.setattr("src.db.list_price_tickers", lambda: ["PETR4"])
    monkeypatch.setattr("src.db.resolve_existing_ticker", lambda t: t)

    runner = CliRunner()
    result = runner.invoke(app, ["compute-returns", "--ticker", "PETR4"])
    assert result.exit_code == 0
    assert "compute-returns" in result.output
    assert "retornos" in result.output
    assert called == [("PETR4", None, None, False)]


def test_compute_returns_date_range(monkeypatch):
    """Passar ``--start`` e ``--end`` deve repassar os valores para o helper."""
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


def test_run_json_output(fake_ingest_success, fake_compute_rows1):
    """Verifica que `main --ticker ... --format json` retorna JSON válido."""
    from src.main import app

    runner = CliRunner()
    result = runner.invoke(
        app, ["--ticker", "PETR4", "--format", "json", "--no-network"]
    )
    assert result.exit_code == 0
    data = json.loads(result.output)

    # Basic summary structure
    assert data["status"] == "success"
    assert isinstance(data.get("job_id"), str)
    assert isinstance(data.get("duration_sec"), (int, float))
    assert isinstance(data.get("tickers"), list)

    # Validate per-ticker payload shape
    ticker_payload = data["tickers"][0]
    assert ticker_payload["ticker"] == "PETR4"
    assert ticker_payload["snapshot_path"] == "snapshots/PETR4-20260215.csv"
    assert ticker_payload["snapshot_checksum"] == "abc"


def test_run_json_output_warning_no_rows(fake_ingest_success, fake_compute_rows0):
    """Verifica o fluxo de warning quando nenhum retorno é calculado."""
    from src.main import app

    runner = CliRunner()
    result = runner.invoke(
        app, ["--ticker", "PETR4", "--format", "json", "--no-network"]
    )

    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["status"] == "warning"
    assert isinstance(data.get("tickers"), list)
    assert data["tickers"][0]["ticker"] == "PETR4"
    assert data["tickers"][0].get("rows_returns") == 0


def test_run_json_output_dry_run_includes_rows(monkeypatch):
    """Verifica que --dry-run gera JSON com rows_ingested preenchido."""
    from src.main import app

    def fake_ingest(*args, **kwargs):
        return {"status": "success", "dry_run": True, "rows": 5}

    monkeypatch.setattr("src.ingest.pipeline.ingest", fake_ingest)

    def fake_compute(*args, **kwargs):
        return {"rows": 1, "persisted": True, "sample_df": None}

    monkeypatch.setattr("src.main._compute_returns_for_ticker", fake_compute)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--ticker",
            "PETR4",
            "--format",
            "json",
            "--dry-run",
            "--no-network",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.output)
    ticker_payload = data["tickers"][0]
    assert ticker_payload["rows_ingested"] == 5


def test_run_json_output_failure_ingest_error(fake_ingest_failure):
    """Verifica o fluxo de failure quando ingest falha."""
    from src.main import app

    runner = CliRunner()
    result = runner.invoke(
        app, ["--ticker", "PETR4", "--format", "json", "--no-network"]
    )

    assert result.exit_code == 2
    data = json.loads(result.output)
    assert data["status"] == "failure"
    assert isinstance(data.get("tickers"), list)
    assert data["tickers"][0]["ticker"] == "PETR4"
    assert data["tickers"][0].get("error_message")


def test_parse_sample_tickers_file(tmp_path):
    """`--sample-tickers` deve aceitar arquivo com tickers listados por linha."""
    from src.main import _parse_sample_tickers

    file_path = tmp_path / "tickers.txt"
    file_path.write_text("PETR4\n# comment\n\nITUB3\n")

    assert _parse_sample_tickers(str(file_path)) == ["PETR4", "ITUB3"]


def test_parse_sample_tickers_empty_file_returns_none(tmp_path):
    """Arquivo vazio ou contendo apenas comentários deve retornar None."""
    from src.main import _parse_sample_tickers

    file_path = tmp_path / "empty.txt"
    file_path.write_text("# nothing here\n\n")

    assert _parse_sample_tickers(str(file_path)) is None


def test_parse_sample_tickers_unreadable_file(monkeypatch, tmp_path):
    """Falha ao ler o arquivo deve propagar a exceção para o usuário."""
    from src.main import _parse_sample_tickers

    file_path = tmp_path / "tickers.txt"
    file_path.write_text("PETR4\n")

    original_read_text = Path.read_text

    def _fail_read_text(self, *args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "read_text", _fail_read_text)

    with pytest.raises(OSError):
        _parse_sample_tickers(str(file_path))

    monkeypatch.setattr(Path, "read_text", original_read_text)


def test_ensure_str_or_none_non_string():
    """_ensure_str_or_none deve retornar None para valores não-string."""
    from src.main import _ensure_str_or_none

    class Dummy:
        pass

    assert _ensure_str_or_none("abc") == "abc"
    assert _ensure_str_or_none(123) is None
    assert _ensure_str_or_none(Dummy()) is None


def test_run_sample_tickers_option(monkeypatch):
    """`--sample-tickers` deve controlar a lista de tickers processados."""
    from src.main import app

    calls = []

    def fake_ingest(
        ticker,
        source="yfinance",
        dry_run=False,
        force_refresh=False,
        **kwargs,
    ):
        calls.append({"ticker": ticker, "source": source, **kwargs})
        return {"status": "success"}

    monkeypatch.setattr("src.ingest.pipeline.ingest", fake_ingest)

    # reduce output noise by also faking compute
    def fake_compute(*args, **kwargs):
        return {"rows": 1, "persisted": True, "sample_df": None}

    monkeypatch.setattr("src.main._compute_returns_for_ticker", fake_compute)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--sample-tickers",
            "PETR4,ITUB3",
            "--no-network",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert {c["ticker"] for c in calls} == {"PETR4", "ITUB3"}


def test_run_max_days_passed_to_ingest(monkeypatch):
    """`--max-days` deve ser traduzido em start/end passados para ingest."""
    # Patch time window resolver to stable values
    import src.ingest.pipeline as pipeline_module
    from src.main import app

    monkeypatch.setattr(
        pipeline_module,
        "_resolve_sample_window",
        lambda d, s, e: ("2020-01-10", "2020-01-17"),
    )

    called = []

    def fake_ingest(
        ticker,
        source="yfinance",
        dry_run=False,
        force_refresh=False,
        **kwargs,
    ):
        called.append(kwargs)
        return {"status": "success"}

    monkeypatch.setattr("src.ingest.pipeline.ingest", fake_ingest)

    def fake_compute(*args, **kwargs):
        return {"rows": 1, "persisted": True, "sample_df": None}

    monkeypatch.setattr("src.main._compute_returns_for_ticker", fake_compute)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--ticker",
            "PETR4",
            "--max-days",
            "7",
            "--no-network",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert called and called[0].get("start") == "2020-01-10"
    assert called[0].get("end") == "2020-01-17"


def test_run_dry_run_flag_propagated_to_ingest_and_compute(monkeypatch):
    """`--dry-run` deve ser propagado até ingest e
    _compute_returns_for_ticker via CLI."""
    import src.ingest.pipeline as pipeline_module
    from src.main import app

    ingest_call = {}
    compute_call = {}

    def fake_ingest(*args, **kwargs):
        ingest_call["kwargs"] = kwargs
        return {"status": "success"}

    def fake_compute_returns_for_ticker(*args, **kwargs):
        compute_call["args"] = args
        compute_call["kwargs"] = kwargs
        return {"rows": 1, "persisted": True, "sample_df": None}

    monkeypatch.setattr(pipeline_module, "ingest", fake_ingest)
    monkeypatch.setattr(
        "src.main._compute_returns_for_ticker", fake_compute_returns_for_ticker
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--ticker",
            "PETR4",
            "--dry-run",
            "--no-network",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert ingest_call.get("kwargs", {}).get("dry_run") is True
    assert compute_call.get("args", (None, None, None, None))[3] is True


def test_run_notebook_invokes_papermill(monkeypatch):
    """`--run-notebook` deve chamar papermill.execute_notebook quando disponível."""
    from src.main import app

    # Fake papermill module
    class FakePM:
        def __init__(self):
            self.called = False
            self.args = None

        def execute_notebook(self, input_nb, output_nb):
            self.called = True
            self.args = (input_nb, output_nb)

    fake_pm = FakePM()
    import sys

    monkeypatch.setitem(sys.modules, "papermill", fake_pm)

    # ensure ingestion pipeline doesn't interfere
    monkeypatch.setattr(
        "src.ingest.pipeline.ingest",
        lambda *a, **k: {"status": "success", "persist": {"rows_processed": 0}},
    )
    monkeypatch.setattr(
        "src.main._compute_returns_for_ticker",
        lambda *args, **kwargs: {"rows": 1, "persisted": True, "sample_df": None},
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--ticker",
            "PETR4",
            "--run-notebook",
            "--format",
            "json",
            "--no-network",
        ],
    )

    assert result.exit_code == 0
    assert fake_pm.called is True
    assert result.output.strip(), "expected output"  # ensure output was emitted


@pytest.mark.skipif(
    importlib.util.find_spec("papermill") is not None,
    reason="papermill installed; cannot test missing dependency path",
)
def test_run_notebook_missing_papermill():
    """`--run-notebook` deve falhar com ImportError quando papermill
    não está instalado."""
    from src.main import app

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--ticker",
            "PETR4",
            "--run-notebook",
            "--format",
            "json",
            "--no-network",
        ],
    )

    assert result.exit_code == 2
    assert "papermill" in result.output.lower()
    assert "instal" in result.output.lower()


def test_run_notebook_runtime_error(monkeypatch):
    """`--run-notebook` deve falhar com código 2 quando papermill lança exceção."""
    from src.main import app

    class FakePMErroring:
        def execute_notebook(self, *args, **kwargs):
            raise RuntimeError("dummy notebook failure")

    import sys

    monkeypatch.setitem(sys.modules, "papermill", FakePMErroring())

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--ticker",
            "PETR4",
            "--run-notebook",
            "--format",
            "json",
            "--no-network",
        ],
    )

    assert result.exit_code == 2
    output = result.output.lower()
    assert (
        "dummy notebook failure" in output
        or "notebook" in output
    )


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
    assert "export-csv" in result.output
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
    # Typer combines stdout/stderr into output on most environments
    assert "não encontrado" in result.output.lower()


def test_ingest_snapshot_command(monkeypatch, tmp_path):
    """Invocar `snapshots ingest` dispara ingest_snapshot() com argumentos."""
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
            "snapshots",
            "ingest",
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


def test_run_supports_sample_tickers_and_max_days(monkeypatch):
    """Verifica os flags --sample-tickers e --max-days são passados ao pipeline."""
    from src.main import app

    called = []

    def fake_ingest(
        ticker, source="yfinance", dry_run=False, force_refresh=False, **kwargs
    ):
        called.append(
            {
                "ticker": ticker,
                "dry_run": dry_run,
                "force_refresh": force_refresh,
                **kwargs,
            }
        )
        return {"status": "success"}

    monkeypatch.setattr("src.ingest.pipeline.ingest", fake_ingest)

    # force deterministic window
    import src.ingest.pipeline as pipeline

    monkeypatch.setattr(
        pipeline,
        "_resolve_sample_window",
        lambda days, start, end: ("2020-01-01", "2020-01-31"),
    )

    # stub retorno calculation to avoid warnings from missing DB data
    monkeypatch.setattr(
        "src.main._compute_returns_for_ticker",
        lambda ticker, start, end, dry_run: {
            "rows": 1,
            "persisted": True,
            "sample_df": None,
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--sample-tickers",
            "PETR4,ITUB3",
            "--max-days",
            "5",
            "--no-network",
        ],
    )
    assert result.exit_code == 0
    assert called, "esperávamos que ingest fosse chamado"
    assert called[0]["ticker"] == "PETR4"
    assert called[1]["ticker"] == "ITUB3"
    assert called[0]["start"] == "2020-01-01"
    assert called[0]["end"] == "2020-01-31"


def test_run_with_run_notebook_flag_invokes_notebook_runner(monkeypatch):
    """`--run-notebook` should invoke the notebook runner after the pipeline."""
    from src.main import app

    # stub ingest and returns to avoid edge cases
    monkeypatch.setattr(
        "src.ingest.pipeline.ingest",
        lambda *args, **kwargs: {"status": "success", "persist": {"rows_processed": 1}},
    )
    monkeypatch.setattr(
        "src.main._compute_returns_for_ticker",
        lambda ticker, start, end, dry_run: {
            "rows": 1,
            "persisted": True,
            "sample_df": None,
        },
    )

    called = {}

    def fake_run_notebook(tickers, job_id, **kwargs):
        called["tickers"] = tickers
        called["job_id"] = job_id
        return {"status": "success"}

    monkeypatch.setattr("src.main._run_notebook", fake_run_notebook)

    runner = CliRunner()
    result = runner.invoke(
        app, ["run", "--ticker", "PETR4", "--run-notebook", "--no-network"]
    )
    assert result.exit_code == 0
    assert called.get("tickers") == ["PETR4"]
    assert "job_id" in called

# UX Playbook (mínimo)

Este documento descreve as expectativas mínimas de UX para CLI, notebooks e uma tela Streamlit simples.

## CLI

- Flags suportadas (exemplos):
  - `--ticker <TICKER>` (ex.: PETR4, ITUB4, BOVA11)
  - `--start_date <YYYY-MM-DD>` (para limitar o intervalo de dados)
  - `--end_date <YYYY-MM-DD>` (para limitar o intervalo de dados)
  - `--force-refresh` (força re-ingest)
  - `--format <text|json>` (formato de saída, padrão `text`)
  - `--no-network` (modo offline para testes/CI usando provider dummy)
  - `--output <path>` (local de saída para `export-csv`)

- Mensagens esperadas (stdout/stderr):
  - Início do processo: `Executando tickers padrão: ...`
  - Success: `Resumo run: sucesso=<n>, falhas=<n>`
  - Warnings: `WARN: Incomplete data for <date>`
  - Errors: `ERROR: Failed to fetch data for <TICKER> - <reason>`

## Notebooks

- Parâmetros esperados (exemplos):
  - `ticker = "PETR4"`
  - `start_date = "2020-01-01"`
  - `end_date = "2020-12-31"`

- Comportamento esperado:
  - Células de preparação carregam o snapshot CSV localizado em `snapshots/`
  - Células de análise computam retornos e geram ao menos um plot de preços ajustados e um plot de retornos

## Streamlit (minimal)

- Telas mínimas:
  1. Tela de seleção de ticker e período
  2. Tela de execução com botão `Run` e área de logs/saídas
  3. Visualização de um gráfico principal e resumo numérico (último preço, retorno 1d)

- Interações esperadas:
  - Ao clicar `Run`, mostrar mensagem `Processing...` e desabilitar inputs até finalizar
  - Exibir mensagens de sucesso/erro conforme CLI

## Exemplos de saída (stdout)

### Exemplo: um ticker por chamada (último `--ticker` vence)

```bash
python main.py --ticker PETR4 --ticker ITUB3 --ticker BBDC4 --no-network
```

**Output esperado (apenas BBDC4 é processado, já que a opção `--ticker` não é listável):**

```
▶ executar: processando ticker=BBDC4 com provider=dummy
… ingestão — ticker=BBDC4 | force_refresh=False | dry_run=False | start=- | end=-
… cálculo de retornos — BBDC4
■ job_id=<UUID> | duration_sec=<n> | sucesso=1 falhas=0
• ticker=BBDC4 snapshot=.../snapshots/BBDC4-<YYYYMMDD>.csv rows=<n>
```

> **Nota:** o CLI normaliza tickers (ex.: converte para maiúsculas e valida o formato). Se você precisa processar vários tickers numa única execução, use `--sample-tickers` (ex.: `--sample-tickers PETR4,ITUB3,BBDC4`) ou execute o comando várias vezes.

## Notas

- Mensagens devem ser concisas e orientadas a troubleshooting
- Use logging estruturado para facilitar parsing em CI/monitoring

## Checklist (mínimo)

- [ ] Documentou flags CLI e mensagens esperadas
- [ ] Documentou parâmetros de notebook e comportamento esperado
- [ ] Documentou telas mínimas do Streamlit e interações

## Limitations and Edge Cases

### CLI limits

- **Max tickers / selection**: `--ticker` accepts a single ticker; to process multiple, use `--sample-tickers` (comma-separated or file). There is no built-in “batch size” limiter, but very large ticker lists may take a long time to complete.
- **Ticker format**: The CLI normalizes tickers (uppercasing and basic validation). Invalid tickers may be rejected or treated as missing data (e.g., `PETR4` is valid, `invalid!` will likely fail validation).
- **Date range (`--start_date` / `--end_date`)**: Dates must be `YYYY-MM-DD`. The code computes a window and enforces `start <= end`. Partial dates (e.g., `2020-01`) are not supported and will fail parsing.
- **`--no-network` behavior**: Uses a dummy provider with fixed sample data. It does not simulate real network errors or retries; network-dependent flags (e.g., those expecting live provider data) will behave differently.

### Edge cases

- **Missing / empty datasets**: If the provider returns no rows for a ticker, the CLI will usually report a warning and continue without writing a snapshot.
- **Network failures and retries**: In normal mode (with network), transient failures may occur; there is no sophisticated retry logic beyond what the adapter implements. The CLI should surface errors and proceed to the next ticker.
- **Partial/invalid input**: Invalid tickers, malformed dates, or missing required flags should result in a clear error message and an exit code indicating failure.

### Notebook constraints

- **CSV schema**: Notebooks expect snapshots in `snapshots/` with a stable schema (date + price columns). If the CSV is missing required fields or has unexpected formatting, notebook cells may error out.
- **Required snapshot fields**: Snapshots should include at least a date column and closing price (same schema used by the pipeline). Missing columns will break the analysis cells.
- **Minimum data window**: Some analysis plots assume a minimum number of points; very short time windows may produce empty charts or warnings.

### Streamlit constraints

- **Supported browsers**: The Streamlit UI is typically supported on modern desktop browsers (Chrome, Firefox, Edge). Mobile usability is not guaranteed.
- **Concurrent users / sessions**: The app is intended for single-user or low-concurrency usage. Multiple simultaneous sessions may compete for the same underlying snapshot/cache resources.
- **Data refresh intervals**: The UI refresh is driven by rerunning the `Run` operation. If the backend is busy, the app shows `Processing...` and disables inputs until completion.
- **Failure behavior**: On failure, the `Processing...` state should clear and an error message should be shown. The UI does not automatically retry.

## Referências
- docs/playbooks/quickstart-ticker.md

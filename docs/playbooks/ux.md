# UX Playbook (minimal)

Objetivo: Descrever mensagens CLI, parâmetros de notebook e telas mínimas do Streamlit para o quickstart.

CLI: mensagens e flags

- `--ticker <TICKER>`: ticker a ser processado (ex.: PETR4.SA)
- `--force-refresh`: força re-fetch e reprocessamento ignorando cache
- `--dry-run`: executa lógica de fetch e mapeamento sem gravar
- `--test-conn --provider <name>`: testa conexão ao provider

Mensagens de sucesso (exemplo)

- `INFO: Fetch complete: 1234 rows from yfinance for PETR4.SA`
- `INFO: Raw saved: raw/yfinance/PETR4.SA-20260216T123456Z.csv`
- `INFO: Snapshot saved: snapshots/PETR4.SA-20260216.csv (sha256: <checksum>)`
- `SUCCESS: Quickstart completed in 00:04:12`

Mensagens de erro (exemplo)

- `ERROR: Fetch failed: timeout from provider yfinance` — inclua `--force-refresh` e reexecute
- `WARN: 12 rows failed schema validation and were flagged in ingest_logs`
- `ERROR: DB write failed: locked database` — retry after short delay or investigate concurrent jobs

Notebook parameters

- Parâmetro `TICKER` (string) — input principal
- Parâmetro `START_DATE` / `END_DATE` (opcional) — para restringir janelas
- Células esperadas:
  - Carregar dados do DB via `db.read_prices(TICKER, start, end)`
  - Calcular returns e plotar séries de preços vs returns
  - Exportar snapshot e exibir checksum

Streamlit POC (telas mínimas)

- Tela principal: input `TICKER` + botão `Run quickstart` (disparar ingest local ou instruir usuário a rodar CLI)
- Tela de status: logs básicos (fetch rows, snapshot path, checksum)
- Tela de visualização: gráfico de preços e gráfico de retornos; botão `Download CSV`

Referências

- docs/playbooks/quickstart-ticker.md
- docs/planning-artifacts/architecture.md

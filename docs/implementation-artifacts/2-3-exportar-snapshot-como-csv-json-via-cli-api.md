---
title: Story 2.3: exportar-snapshot-como-csv-json-via-cli-api
status: ready-for-dev
story_id: 2.3
story_key: 2-3-exportar-snapshot-como-csv-json-via-cli-api
generated_by: bmad/create-story
generated_at: 2026-02-17T00:00:00Z
---

# Story 2.3: exportar-snapshot-como-csv-json-via-cli-api

Status: ready-for-dev

## Story

Como Operador/Usuário,
eu quero exportar snapshots dos dados persistidos em CSV e JSON via CLI e API,
para que eu possa consumir, compartilhar e comparar conjuntos de dados (backup, análise, ingest externas).

## Acceptance Criteria

1. Dado um ticker (ex.: PETR4.SA) e intervalo (start/end) o sistema gera um snapshot contendo todas as linhas canônicas disponíveis no período solicitado.
2. O snapshot é exportável em `csv` e `json` via CLI (`poetry run main snapshots export`) e via API (se existir uma rota HTTP bem definida).
3. Cada snapshot gerado é salvo em `snapshots/<ticker>/<ticker>-<YYYYMMDDTHHMMSSZ>.<ext>` e inclui metadados com `created_at`, `rows`, `checksum_sha256`.
4. Para `csv` o arquivo inclui cabeçalho com colunas canônicas (`ticker,date,open,high,low,close,adj_close,volume,source,fetched_at`); para `json` usa NDJSON ou array (documentar comportamento).
5. O checksum SHA256 do arquivo é calculado e gravado em arquivo adjunto `<filename>.checksum` e também registrado em tabela `snapshots` ou `metadata` no DB (`snapshots` table), conforme design existente (ver FR13/FR15 em docs/planning-artifacts/epics.md).
6. A operação é idempotente para a mesma combinação (ticker, timestamp-derivation-params) — reexecuções com `--force` substituem arquivos e atualizam metadados; execuções sem `--force` não sobrescrevem por padrão.
7. Há testes unitários e um teste de integração leve (mocked DB) que valida: geração de arquivo, conteúdo mínimo, cálculo de checksum e gravação de metadados.

## Tasks / Subtasks

- [ ] Implementar função `snapshots.generate_snapshot(ticker, start=None, end=None, format='csv', chunked=True)` que lê de `dados/data.db` e retorna/persiste arquivo
  - [ ] Ler preços canônicos via `db.read_prices(ticker, start, end)` ou SQL equivalente
  - [ ] Normalizar colunas para esquema canônico e ordenar por `date`
  - [ ] Serializar em CSV/JSON com flag `chunked` quando dataset grande
  - [ ] Calcular SHA256 do arquivo produzido e gravar `<file>.checksum`
  - [ ] Persistir metadados em tabela `snapshots` ou `metadata` (created_at, rows, checksum, path)
- [ ] Adicionar subcomando CLI `snapshots export --ticker <TICKER> [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--format csv|json] [--output PATH] [--force]`
- [ ] (Opcional) Implementar rota HTTP `GET /api/snapshots?ticker=&start=&end=&format=` que retorna URL para download ou stream direto
- [ ] Implementar testes unitários (pytest) cobrindo geração + checksum + metadata persistence
- [ ] Atualizar `README` e `docs/playbooks/quickstart-ticker.md` com exemplos de uso e caminhos
- [ ] Adicionar nota operacional sobre permissões (`chmod 600` para arquivos sensíveis, e instruções de retenção)

## Dev Notes

- Leitura de dados: usar API interna `db.read_prices(...)` ou acesso direto com `pandas.read_sql_query` apontando para `dados/data.db`.
- Serialização: para CSV usar `DataFrame.to_csv(path, index=False)` e para JSON preferir `orient='records'` (ou NDJSON para streaming). Documentar formato e trade-offs.
- Checksum: calcular SHA256 no arquivo final (calcular no stream para grandes arquivos). Salvar em `<file>.checksum` e registrar em DB.
- Performance: suportar `chunked=True` para não carregar todo o dataset na memória quando > 1M rows. Testar com dados sintetizados.
- Segurança/Permissões: gravar arquivos em `snapshots/` com permissões seguras por padrão e registrar caminho absoluto relativo ao `snapshot_dir` configurado via `SNAPSHOT_DIR`.

### Project Structure Notes

- Suggested implementation files:
  - `src/snapshots.py` — funções de geração e helpers (checksum, path)
  - `src/cli/snapshots.py` — Typer subcomando `snapshots export`
  - `src/api/snapshots.py` — (se API for necessária) endpoint leve que usa a mesma função
  - `tests/test_snapshots.py` — unit + integration mocked DB

### References

- Epic/story mapping and requirements: docs/planning-artifacts/epics.md (FR13, FR14, FR15)
- Sprint tracking: docs/implementation-artifacts/sprint-status.yaml

## Dev Agent Record

### Agent Model Used

automation-agent (LLM-assisted)

### Completion Notes List

- Arquivo criado a partir de template `create-story/template.md` e contexto em `docs/planning-artifacts/epics.md`.

### File List

- src/snapshots.py (proposto)
- src/cli/snapshots.py (proposto)
- tests/test_snapshots.py (proposto)

---

## Story 1.6: Persistir dados canônicos no SQLite com upsert por (ticker, date)

Status: ready-for-dev

## Story

As a Developer,
I want a DB layer that writes canonical rows to `dados/data.db` with idempotent upsert semantics,
so that repeated ingests do not create duplicate records and the database remains consistent.

## Acceptance Criteria

1. Dado um `DataFrame` canônico, a camada de BD grava/atualiza linhas na tabela `prices` por `(ticker, date)` (upsert) e reflete os valores mais recentes.
2. `db.read_prices(ticker, start, end)` retorna as linhas esperadas para consultas por intervalo.
3. Escritas registram `schema_version` em `metadata` para rastreabilidade.
4. Implementação documenta claramente a estratégia de upsert (ex.: `ON CONFLICT` / `INSERT OR REPLACE`) e limitações do SQLite.

## Tasks / Subtasks

- [ ] Implementar módulo `src.db` com funções `write_prices(df: pd.DataFrame, ticker: str)` e `read_prices(ticker, start=None, end=None)`
  - [ ] Definir esquema da tabela `prices` com PK (`ticker`, `date`) e colunas: `open, high, low, close, volume, source, fetched_at, raw_checksum`
  - [ ] Nota: `adj_close` pode ser emitido pelo mapper para uso em cálculos (ex.: retornos), mas não é persistido por padrão. Se for necessário persistir `adj_close`, atualize `docs/schema.json` e introduza versão/migração apropriada.
  - [ ] Implementar upsert por `(ticker, date)` usando SQLAlchemy/Core ou `pandas.to_sql` + `ON CONFLICT` raw SQL
  - [ ] Gravar/atualizar `schema_version` na tabela `metadata` a cada alteração importante do esquema
  - [ ] Adicionar permissões recomendadas (documentar `chmod 600` para `dados/data.db`)
  - [ ] Escrever testes unitários usando SQLite in-memory que validem idempotência (inserir 2x → mesma contagem)
- [ ] Documentar o que foi implantado nessa etapa em `docs/sprint-reports` conforme definido no FR28 (`docs/planning-artifacts/prd.md`)

## Dev Notes

- DB location: `dados/data.db` (local, SQLite). Favor preservar convenção do projeto.
- Tables mínimas envolvidas: `prices`, `returns`, `ingest_logs`, `snapshots`, `metadata`.
- Upsert semantics: prefer `INSERT INTO prices (...) VALUES (...) ON CONFLICT (ticker, date) DO UPDATE SET ...` (SQLite >= 3.24 supports `ON CONFLICT`/`UPSERT`).
- Recomendações de implementação:
  - Use SQLAlchemy Core/ORM para abstração; executar raw SQL `ON CONFLICT` quando necessário para compatibilidade e performance.
  - Use `pandas` para transformação e `df.to_sql()` somente para cargas iniciais; para upserts por linha use `executemany` com `ON CONFLICT` ou `INSERT OR REPLACE` (avaliar impacto em campos não enviados).
  - Serialize `fetched_at` em UTC ISO8601.
  - Calcule e grave `raw_checksum` (SHA256) para cada payload original quando disponível.

### Testing

- Unit tests: `tests/test_db_write.py` cobrindo:
  - escrita inicial e leitura
  - upsert idempotente (duas escritas não duplicam)
  - gravação de `schema_version` e metadados
- Integração: fixture que popula um `DataFrame` de exemplo (use `tests/fixtures/sample_ticker.csv`) e executa `write_prices`, verifica `read_prices` e snapshot gerado.

### Project Structure Notes

- Implementar código em `src/` seguindo convenções existentes: `src.dados_b3`, `src.retorno`, `src.db` (novo).
- Tests em `tests/` com fixtures em `tests/fixtures/`.
- Documentar API em `docs/` e referenciar em `docs/planning-artifacts/epics.md` e `docs/planning-artifacts/prd.md`.

### References

- Source: [docs/planning-artifacts/epics.md](docs/planning-artifacts/epics.md) — Story 1.6 description and acceptance criteria.
- Source: [docs/planning-artifacts/prd.md](docs/planning-artifacts/prd.md) — DB schema recommendations and constraints.
- Source: [docs/planning-artifacts/architecture.md](docs/planning-artifacts/architecture.md) — architecture constraints and stack choices.

## Dev Agent Record

### Agent Model Used
GPT-5 mini

### Completion Notes List

- Story file generated from `template.md` and epics/prd analysis.
- Acceptance criteria and tasks populated from `docs/planning-artifacts/epics.md` Story 1.6.
- Dev guardrails added: SQLAlchemy + pandas guidance, upsert patterns, testing notes.

### File List

- docs/planning-artifacts/epics.md (source)
- docs/planning-artifacts/prd.md (source)

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/119

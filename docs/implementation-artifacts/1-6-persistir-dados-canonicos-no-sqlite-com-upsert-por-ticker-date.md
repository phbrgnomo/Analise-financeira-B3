## Story 1.6: Persistir dados canônicos no SQLite com upsert por (ticker, date)

Status: review

## Story

As a Developer,
I want a DB layer that writes canonical rows to `dados/data.db` with idempotent upsert semantics,
so that repeated ingests do not create duplicate records and the database remains consistent.

## Acceptance Criteria

1. Dado um `DataFrame` canônico, a camada de BD grava/atualiza linhas na tabela `prices` por `(ticker, date)` (upsert) e reflete os valores mais recentes.
2. `db.read_prices(ticker, start, end)` retorna as linhas esperadas para consultas por intervalo.
3. Escritas registram `schema_version` em `metadata` para rastreabilidade.
4. Implementação documenta claramente a estratégia de upsert (ex.: `ON CONFLICT` / `INSERT OR REPLACE`) e limitações do SQLite.

## Exemplos de Uso

Abaixo seguem exemplos simples de como utilizar a nova API de BD em `src.db`.

- Exemplo de `DataFrame` canônico esperado (colunas essenciais):

```python
import pandas as pd
from src import db

# Exemplo mínimo de DataFrame canônico
df = pd.DataFrame({
  "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
  "open": [10.0, 10.5],
  "high": [10.2, 10.8],
  "low": [9.8, 10.0],
  "close": [10.1, 10.6],
  "volume": [1000, 1500],
  # Campos auxiliares como `source`, `fetched_at` e `raw_checksum` podem
  # ser preenchidos pelo pipeline ou pelo chamador quando disponíveis.
  "source": ["yfinance", "yfinance"],
})

# Persistir (idempotente por (ticker, date))
db.write_prices(df, ticker="PETR4")
```

- Leitura completa e por intervalo:

```python
# Ler todas as linhas para um ticker
all_rows = db.read_prices("PETR4")

# Ler por intervalo de datas (inclusive)
range_rows = db.read_prices("PETR4", start="2024-01-01", end="2024-01-31")
```

Observações:

- O `DataFrame` de entrada deve conter pelo menos as colunas `date, open, high, low, close, volume`.
- A coluna `date` pode ser uma coluna do `DataFrame` (será interpretada) ou o índice ser do tipo `DatetimeIndex`.
- `write_prices` aplica comportamento de upsert por `(ticker, date)`: chamar `write_prices` repetidamente com o mesmo `ticker` e as mesmas datas é idempotente — registros duplicados não serão criados; valores existentes serão atualizados conforme a política definida (`ON CONFLICT` / `INSERT OR REPLACE`).
- `read_prices` retorna um `DataFrame` com a coluna `date` como índice (`DatetimeIndex`).


## Tasks / Subtasks

- [x] Implementar módulo `src.db` com funções `write_prices(df: pd.DataFrame, ticker: str)` e `read_prices(ticker, start=None, end=None)`
  - [x] Definir esquema da tabela `prices` com PK (`ticker`, `date`) e colunas: `open, high, low, close, volume, source, fetched_at, raw_checksum`
  - [x] Nota: `adj_close` pode ser emitido pelo mapper para uso em cálculos (ex.: retornos), mas não é persistido por padrão. Se for necessário persistir `adj_close`, atualize `docs/schema.json` e introduza versão/migração apropriada.
  - [x] Implementar upsert por `(ticker, date)` usando SQLAlchemy/Core ou `pandas.to_sql` + `ON CONFLICT` raw SQL
  - [x] Gravar/atualizar `schema_version` na tabela `metadata` a cada alteração importante do esquema
  - [x] Adicionar permissões recomendadas (documentar `chmod 600` para `dados/data.db`)
  - [x] Escrever testes unitários usando SQLite in-memory que validem idempotência (inserir 2x → mesma contagem)
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

- Implementation summary:
  - Added `src/db.py` implementing `write_prices` and `read_prices` with SQLite upsert semantics using `ON CONFLICT (ticker,date)`.
  - Wrote `tests/test_db_write.py` covering initial write, idempotent upsert (write twice → same row count), and metadata `schema_version` persistence.
  - Ran full test suite: `pytest` → 89 passed, 0 failed (local run).

### File List

- docs/planning-artifacts/epics.md (source)
- docs/planning-artifacts/prd.md (source)

### Updated Files (this session)

- src/db.py
- tests/test_db_write.py

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/119

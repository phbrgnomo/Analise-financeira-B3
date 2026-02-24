# Convenções de Retornos e Persistência

Resumo curto das convenções usadas no projeto para cálculo e persistência de retornos.

- Convenção de anualização: 252 dias de negociação por ano (constante TRADING_DAYS = 252).
  - Use 252 para anualizar médias e volatilidade (ex.: desvio_anual = desvio_diario * sqrt(252)).
  - Para retorno médio diário convertido para anual: conv_retorno(mean_daily, 252).

- Campo usado para cálculo: preferir `adj_close` quando disponível; fallback para `close`/`Close`.
  - A função `compute_returns` no módulo `src.retorno` escolhe automaticamente a melhor coluna.

- Persistência/Upsert (SQLite):
  - Preferir `ON CONFLICT(...) DO UPDATE` quando runtime SQLite suportar (>= 3.24.0) para preservar metadados.
  - Exemplo SQL (preferido):

```sql
INSERT INTO returns (ticker, date, return, return_type, created_at)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT(ticker, date, return_type) DO UPDATE SET
  return = excluded.return,
  created_at = COALESCE(returns.created_at, excluded.created_at);
```

- Fallback: `INSERT OR REPLACE` quando `ON CONFLICT` não estiver disponível. Atenção: `INSERT OR REPLACE` sobrescreve a linha inteira e pode perder `created_at` original.

- Schema esperado da tabela `returns` (mínimo):
  - `ticker` TEXT
  - `date` TEXT (YYYY-MM-DD)
  - `return` REAL
  - `return_type` TEXT
  - `created_at` TEXT (ISO 8601 UTC)
  - UNIQUE(ticker, date, return_type)

- Telemetria: `record_snapshot_metadata` grava um JSON em `snapshots` com `job_id`, `action`, `ticker`, `rows_written`, `duration_ms`, `created_at`.

- Implementação preferida: calcular retornos com `pandas` (Series.pct_change()), montar DataFrame com colunas necessárias e persistir via camada do projeto `src.db.write_returns()` que aplica upsert de forma idempotente.

```py
# exemplo mínimo
returns = prices_series.pct_change().dropna()
out = returns.rename('return').to_frame()
out['ticker'] = ticker
out['return_type'] = 'daily'
out['created_at'] = datetime.now(timezone.utc).isoformat()
# delegar persistência
src.db.write_returns(out, conn=conn)
```

Referência: `docs/implementation-artifacts/1-7-implementar-transformacao-de-retornos-e-persistencia-em-returns.md`.

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

## Quickstart para consumidores

1. Rodar o CLI (dry-run):

```bash
poetry run python -m src.main compute-returns --ticker PETR4.SA --dry-run
```

2. Persistir retornos e checar algumas linhas:

```bash
poetry run python -m src.main compute-returns --ticker PETR4.SA
sqlite3 dados/data.db "SELECT ticker, date, return, created_at FROM returns WHERE ticker='PETR4.SA' ORDER BY date DESC LIMIT 5;"
```

3. Exemplo rápido em Python (pandas):

```py
import sqlite3
import pandas as pd
from datetime import timezone, datetime

conn = sqlite3.connect('dados/data.db')
df = pd.read_sql_query("SELECT date, return FROM returns WHERE ticker='PETR4.SA' ORDER BY date", conn, parse_dates=['date']).set_index('date')
df['cum_return'] = (1 + df['return']).cumprod() - 1
print(df.tail())
```

## Exemplos SQL úteis

- Últimos 100 retornos de um ativo:

```sql
SELECT ticker, date, return
FROM returns
WHERE ticker = 'PETR4'
ORDER BY date DESC
LIMIT 100;
```

- Média e desvio por ano:

```sql
SELECT ticker, AVG(return) AS mean_return, (AVG(return*return)-AVG(return)*AVG(return)) AS var_return
FROM returns
WHERE date BETWEEN '2025-01-01' AND '2025-12-31'
GROUP BY ticker;
```

- Retorno acumulado (geométrico) por janela:

```sql
SELECT ticker, date,
  EXP(SUM(LOG(1 + return)) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) - 1
  AS cumulative_return
FROM returns;
```

## Nota de compatibilidade SQLite

Recomendamos executar com SQLite >= 3.24.0 para garantir suporte a `ON CONFLICT ... DO UPDATE`.
Em ambientes onde isso não é possível, a implementação usa um fallback transacional (UPDATE→INSERT) para preservar metadados; ainda assim avaliar migrar para Postgres em cenários com múltiplos escritores concorrentes.

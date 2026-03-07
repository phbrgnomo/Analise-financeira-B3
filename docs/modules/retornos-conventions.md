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
INSERT INTO returns (ticker, date, return_value, return_type, created_at)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT(ticker, date, return_type) DO UPDATE SET
  return_value = excluded.return_value,
  created_at = COALESCE(returns.created_at, excluded.created_at);
```

- Fallback: `INSERT OR REPLACE` quando `ON CONFLICT` não estiver disponível. Atenção: `INSERT OR REPLACE` sobrescreve a linha inteira e pode perder `created_at` original.

- Schema esperado da tabela `returns` (mínimo):
  - `ticker` TEXT
  - `date` TEXT (YYYY-MM-DD)
  - `return_value` REAL
  - `return_type` TEXT
  - `created_at` TEXT (ISO 8601 UTC)
  - UNIQUE(ticker, date, return_type)

- Telemetria: `record_snapshot_metadata` grava um JSON em `snapshots` com `job_id`, `action`, `ticker`, `rows_written`, `duration_ms`, `created_at`.

- Implementação preferida: calcular retornos com `pandas` (Series.pct_change()), montar DataFrame com colunas necessárias e persistir via camada do projeto `src.db.write_returns()` que aplica upsert de forma idempotente.

```py
# exemplo mínimo
# Observação: `prices_series`, `ticker` e `conn` são assumidos como
# definidos anteriormente (por ex. `prices_series` é uma pd.Series de preços,
# `ticker` é o símbolo string e `conn` é uma sqlite3.Connection).
from datetime import datetime, timezone
import src.db as db  # ou: from src.db import write_returns

returns = prices_series.pct_change().dropna()
out = returns.rename('return_value').to_frame()
out['ticker'] = ticker
out['return_type'] = 'daily'
out['created_at'] = datetime.now(timezone.utc).isoformat()
# delegar persistência (escolha: usar db.write_returns ou importar diretamente)
db.write_returns(out, conn=conn)
```

Referência: `docs/implementation-artifacts/1-7-implementar-transformacao-de-retornos-e-persistencia-em-returns.md`.

## Compatibilidade e migração

> **Aviso de depreciação**: a coluna `return` usada em versões antigas está
> oficialmente *deprecated* a partir de **2026‑06‑30** e será **removida em
> 2026‑12‑31**. Novos cálculos, tabelas e consultas devem usar
> `return_value` como nome canônico. A view `returns_compat` existe apenas como
> alias temporário para facilitar a transição; não deve ser usada em código
> produtivo a longo prazo.

Observação: o nome canônico da coluna persistida usada pelo código do projeto
é `return_value`. Alguns exemplos antigos e notebooks podem referir-se à
coluna como `return` ou `Return`. A seguir estão estratégias de compatibilidade
e uma proposta de migração completa quando for necessário renomear a coluna
no banco.

### Compatibilidade enquanto a coluna `return` ainda existir

- Consulta compatível (mantém `return_value` como fonte da verdade, expõe alias):

```sql
SELECT date, return_value AS return
FROM returns
WHERE ticker = 'PETR4.SA'
ORDER BY date;
```

- Criar uma view de compatibilidade (não altera dados, apenas expõe o alias):

```sql
CREATE VIEW IF NOT EXISTS returns_compat AS
SELECT ticker, date, return_value AS "return", return_type, created_at
FROM returns;
```

### Plano de migração da tabela `returns`

Ao chegar a hora de remover a coluna `return` do esquema, a equipe pode
escolher uma das duas abordagens abaixo.

1. **Tabela nova + cópia de linhas** (recomendado para sqlite sem ALTER):

```sql
-- criar nova tabela com o nome correto
CREATE TABLE returns_new (
    ticker TEXT,
    date TEXT,
    return_value REAL,
    return_type TEXT,
    created_at TEXT,
    UNIQUE(ticker, date, return_type)
);

-- copiar dados renomeando a coluna
INSERT INTO returns_new (ticker, date, return_value, return_type, created_at)
SELECT ticker, date, "return" AS return_value, return_type, created_at
FROM returns;

-- substituir tabela antiga
DROP TABLE returns;
ALTER TABLE returns_new RENAME TO returns;
```

2. **ALTER TABLE RENAME COLUMN** (quando o banco suportar diretamente):

```sql
ALTER TABLE returns RENAME COLUMN "return" TO return_value;
```

Ambas opções convertem todos os registros existentes; escolha baseado no
suporte do engine e na facilidade de rollback.

### Validação da migração

Após realizar qualquer migração, verifique via CI/revisão:

- ✅ **Contagem de linhas**: `SELECT COUNT(*)` na tabela antiga versus nova deve
  coincidir.
- ✅ **Spot‑checks**: executar alguns `SELECT` manuais para garantir que valores
  de `return_value` correspondem ao que anteriormente era exposto como
  `return`.
- ✅ **View de compatibilidade**: `SELECT * FROM returns_compat LIMIT 5` ainda
  funciona corretamente até a remoção final.
- ✅ **Testes e CI**: atualizar fixtures e testes que mencionam `return`.
- ✅ **Busca no codebase**: rodar `grep -R "\breturn\b" -n src` e trocar
  referências legadas por `return_value` (exceto quando o contexto é a palavra
  genérica return em código Python).

Essas etapas permitem que revisores acompanhem e aprovem a mudança de maneira
clara e segura.

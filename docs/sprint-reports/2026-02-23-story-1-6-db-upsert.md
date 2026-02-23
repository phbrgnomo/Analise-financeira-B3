---
title: "Story 1.6 — Persistência canônica em SQLite (upsert por ticker,date)"
date: 2026-02-23
story: 1-6-persistir-dados-canonicos-no-sqlite-com-upsert-por-ticker-date
status: delivered
---

Resumo
-
Implementação da camada de persistência SQLite que grava linhas canônicas na tabela `prices` com semântica idempotente de upsert por `(ticker, date)`. O código principal foi adicionado em [src/db.py](src/db.py) e os testes unitários em [tests/test_db_write.py](tests/test_db_write.py). A story foi atualizada em [docs/implementation-artifacts/1-6-persistir-dados-canonicos-no-sqlite-com-upsert-por-ticker-date.md](docs/implementation-artifacts/1-6-persistir-dados-canonicos-no-sqlite-com-upsert-por-ticker-date.md).

Objetivos atendidos
-
- Gravar/atualizar linhas na tabela `prices` por `(ticker, date)` (upsert).
- Fornecer `read_prices(ticker, start=None, end=None)` para consultas por intervalo.
- Registrar `schema_version` em `metadata` para rastreabilidade.
- Garantir idempotência (escrever o mesmo DataFrame duas vezes não cria duplicatas).

Onde olhar
-
- Implementação: [src/db.py](src/db.py)
- Testes: [tests/test_db_write.py](tests/test_db_write.py)
- Story / ACs: [docs/implementation-artifacts/1-6-persistir-dados-canonicos-no-sqlite-com-upsert-por-ticker-date.md](docs/implementation-artifacts/1-6-persistir-dados-canonicos-no-sqlite-com-upsert-por-ticker-date.md)

Design e decisões principais
-
- Esquema mínimo criado:
  - tabela `prices` com PK composta `(ticker, date)` e colunas: `open, high, low, close, volume, source, fetched_at, raw_checksum`.
  - tabela `metadata` (key/value) armazena `schema_version`.
- Estratégia de upsert: usamos SQL `INSERT ... ON CONFLICT(ticker,date) DO UPDATE SET ...` para atualizar campos com os valores mais recentes quando a mesma combinação `(ticker,date)` já existir.
- `raw_checksum`: SHA256 calculado por linha a partir dos campos relevantes (ticker, date, preços, volume, source) para facilitar detecção de mudanças no payload original.
- `fetched_at` gravado em formato ISO8601 UTC (usando datetime.now(timezone.utc).isoformat()).
- A implementação aceita um `sqlite3.Connection` in-memory para testes e `db_path` para uso em disco (padrão: dados/data.db).

Exemplo de uso (Python)
-
```py
from src import db
import pandas as pd

# df: DataFrame com índice DatetimeIndex ou coluna 'date' e colunas open,high,low,close,volume
db.write_prices(df, "PETR4.SA")
df2 = db.read_prices("PETR4.SA", start="2023-01-02", end="2023-01-06")
```

Testes e verificação
-
- Testes adicionados: [tests/test_db_write.py](tests/test_db_write.py) — cobre escrita inicial, upsert idempotente (escrever 2x → mesma contagem) e presença de `schema_version` em `metadata`.
- Como rodar localmente:
```bash
poetry run pytest -q
```
- Resultado local (execução feita durante implementação): `89 passed, 0 failed`.

Permissões e operação
-
- Banco por convenção: `dados/data.db`.
- Recomendação de permissão: `chmod 600 dados/data.db` quando o arquivo for criado em produção para proteger dados sensíveis.

Limitações e observações
- Upsert com `ON CONFLICT` requer SQLite >= 3.24 para comportamento UPSERT; a implementação agora detecta a versão do SQLite em runtime e, quando não suportado, realiza fallback para `INSERT OR REPLACE` (com aviso). Documente o risco do fallback (substituição completa da linha) e, se necessário, atualize o ambiente/CI para usar SQLite >= 3.24.
- `INSERT OR REPLACE` foi evitado por padrão devido a possíveis efeitos colaterais (substituição completa da linha); quando usado como fallback, há um aviso explicando o risco.
- `fetched_at` agora é gerado como timestamp timezone-aware UTC (`datetime.now(timezone.utc).isoformat()`), evitando ambiguidade de timezone.
- Se for necessário persistir `adj_close` ou outros campos, atualize `docs/schema.json` e introduza migração/versão de esquema.

Próximos passos recomendados
-
- Escrever uma migração / versão do esquema se a tabela `prices` for expandida. Documentar no arquivo `docs/schema.md`.
- Adicionar um utilitário CLI para inspecionar/compactar o DB (vacuum, permissões, backup).
- `fetched_at` é agora timezone-aware em UTC (`datetime.now(timezone.utc).isoformat()`); padronize este formato no projeto e documente-o em `docs/schema.md` para evitar inconsistências.
- Abrir PR com os arquivos criados e este relatório de sprint.

Contato
-
Para dúvidas sobre implementação, verifique [src/db.py](src/db.py) ou pergunte aqui que eu explico detalhes do SQL e design.

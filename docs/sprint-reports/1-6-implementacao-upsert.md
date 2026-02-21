# Sprint Report — Story 1.6: Persistir dados canônicos no SQLite com upsert por (ticker, date)

Resumo da implementação

- Implementado o módulo `src/db.py` com funções públicas:
  - `create_tables_if_not_exists(engine=None)`
  - `write_prices(df: pd.DataFrame, ticker: str, engine=None, schema_version: Optional[str]=None)`
  - `read_prices(ticker: str, start=None, end=None, engine=None)`

- Estratégia de upsert: uso de `INSERT ... ON CONFLICT (ticker, date) DO UPDATE SET ...` via SQLAlchemy Core (dialeto SQLite).
- Cada linha grava `fetched_at` (UTC) e `raw_checksum` (SHA256) para rastreabilidade.
- `schema_version` é gravado/atualizado na tabela `metadata` quando fornecido.

Limitações e observações

- O `ON CONFLICT` do SQLite funciona em versões >= 3.24; em ambientes com versões antigas do SQLite é necessário fallback (ex.: `INSERT OR REPLACE`).
- Concorrência/locks: SQLite é um banco local com limites de concorrência; para cargas concorrentes avaliar locking/external coordination por ticker (ex.: lock simples).
- Performance: upserts por linha são mais lentos que cargas em lote; para grandes cargas preferir estratégias de staging + swap.

Permissões recomendadas

- Recomendação operacional: o ficheiro de BD `dados/data.db` deve ter permissões mínimas, por exemplo `chmod 600 dados/data.db`, para proteger dados sensíveis em ambiente local.

Como executar testes

- Ambiente (local): `poetry install`
- Executar testes unitários: `poetry run pytest tests/test_db_write.py -q`

Arquivos adicionados/modificados

- `src/db.py` — implementação do layer de persistência e upsert
- `tests/test_db_write.py` — testes unitários para escrita, upsert idempotente e metadata

Logs de execução

- Testes locais (unitários) executados e passaram com sucesso para os cenários adicionados.

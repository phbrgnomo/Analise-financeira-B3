# Sprint Report — Story 1.6: Persistir dados canônicos no SQLite com upsert por (ticker, date)

Justificativa das decisões

- Uso de SQLAlchemy Core + `ON CONFLICT`: fornece abstração de esquema e SQL parametrizado; o `ON CONFLICT` permite um upsert atômico no SQLite, reduzindo risco de duplicação e condições de corrida simples.
- Upsert por linha (INSERT ... ON CONFLICT DO UPDATE) em vez de `pandas.to_sql`: `to_sql` facilita cargas em lote, mas não dá controle fino de upserts; usar Core/`executemany` permite atualizar apenas colunas necessárias, preservar campos e calcular checksums por linha.
- `fetched_at` em UTC ISO8601: padroniza timestamps, evitando ambiguidades de fuso horário e facilitando comparações entre fontes e sessões.
- `raw_checksum` (SHA256): permite detectar alterações no payload original independentemente de timestamps, útil para auditoria e reprocessamento incremental.
- `schema_version` em `metadata`: traz rastreabilidade da versão do esquema aplicada aos dados, facilitando diagnósticos e migrações futuras; somente gravado quando fornecido para evitar sobrescritas indesejadas.
- Testes com SQLite in-memory: rápidos, isolados e determinísticos; reproduzem o comportamento do engine SQLite usado localmente sem criar artefatos no disco, adequado para CI.
- `create_tables_if_not_exists` via SQLAlchemy metadata: centraliza definição do esquema, facilita manutenção e minimiza discrepâncias entre ambientes.
- Permissões (`chmod 600` em dados/data.db): mitigação operacional básica para proteger dados locais sensíveis.



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

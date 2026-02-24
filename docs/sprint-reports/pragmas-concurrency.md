## PRAGMAs & Concurrency: WAL + busy_timeout

Resumo das mudanças aplicadas para reduzir riscos de concorrência com SQLite:

- `src/db.py`:
  - `_connect()` agora usa `sqlite3.connect(..., timeout=30.0)` e aplica em modo *best-effort*:
    - `PRAGMA journal_mode=WAL;`
    - `PRAGMA busy_timeout=30000;`
    - Falhas ao aplicar PRAGMAs são silenciosamente ignoradas para não quebrar testes in-memory.
  - `init_db()` reaplica PRAGMAs após criar o schema, também em modo best-effort.

- Testes:
  - Adicionado `tests/test_concurrency_sqlite.py` que cria um DB file-backed em `tmp_path`, executa múltiplos writers em paralelo usando `ThreadPoolExecutor` e valida que não ocorrem erros de lock e que linhas são persistidas.
  - O teste pula quando a versão do SQLite no runtime é anterior a `3.24.0` (UPSERT/WAL mínimo recomendado).

Decisões e recomendações:

- Usar `WAL` e `busy_timeout` como configuração padrão *best-effort* para conexões com arquivo.
- Não alterar `check_same_thread` globalmente; cada thread/processo deve abrir sua própria conexão.
- Testes de concorrência devem usar DB file em `tmp_path` (não `:memory:`).

Notas de implantação:

- CI foi atualizado para imprimir `sqlite3.sqlite_version` e executar o teste de concorrência no job `acceptance` (best-effort). Se o runner tiver SQLite antigo, o teste será pulado localmente ou poderá ser tratado como não-blocking no CI.

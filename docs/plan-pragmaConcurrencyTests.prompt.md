Plan: PRAGMA + Concurrency Tests

Crie o branch `feature/pragmas-concurrency-tests` e implemente as seguintes mudanças para mitigar riscos de concorrência com SQLite e validar a robustez do sistema:

TL;DR — Aplicar PRAGMAs (WAL + busy_timeout) nas conexões de arquivo em `src/db.py` e adicionar testes de concorrência file-backed (`tests/test_concurrency_sqlite.py`) que usam `tmp_path` + múltiplas conexões. Winston implementa e revisa mudanças no engine; Quinn projeta e valida os testes/CI.

Steps - Crie um #tool:todo para cada passo e inicie a execução:
0. Crie o branch `feature/pragmas-concurrency-tests` e implemente as seguintes mudanças para mitigar riscos de concorrência com SQLite e validar a robustez do sistema:
1. **Analisar pontos de alteração**: revisar `src/db.py` ([src/db.py](src/db.py#L179-L205), [src/db.py](src/db.py#L137-L149), [src/db.py](src/db.py#L252-L268)) e `scripts/init_ingest_db.py` para entender init e pontos que criam conexões de arquivo. (Owner: Winston)
2. **Aplicar PRAGMAs no _connect/init_db**: modificar `_connect()` e `init_db()` para:
   - abrir conexões com `sqlite3.connect(db_path, timeout=30.0)` (Python-side timeout);
   - executar em best-effort: `PRAGMA journal_mode=WAL;` e `PRAGMA busy_timeout=30000;` imediatamente após abrir a conexão (envolver em try/except para não quebrar in-memory tests).
   - garantir `init_db()` também aplica PRAGMAs após criar o arquivo/schema. (Owner: Winston) — editar `src/db.py`.
3. **Preservar comportamento dos testes existentes**: manter in-memory tests inalterados (não executar PRAGMAs que quebrem execução). Aplicação deve ser best-effort (ignorar falhas de PRAGMA). (Owner: Winston + Quinn)
4. **Adicionar testes de concorrência file-backed**: criar `tests/test_concurrency_sqlite.py` que:
   - usa `tmp_path` para criar `data.db` e chama `src.db.init_db(str(db_file))`;
   - executa vários writers em paralelo (ThreadPoolExecutor ou ProcessPoolExecutor), cada worker abrindo sua própria conexão `sqlite3.connect(str(db_file), timeout=30.0)` e escrevendo pequenas quantidades via `src.db.write_prices(...)` ou `executemany`;
   - verifica que não houve `sqlite3.OperationalError: database is locked` e que linhas esperadas foram persistidas;
   - verifica opcionalmente `PRAGMA journal_mode` == 'wal' e pula/xfail o teste se `sqlite3.sqlite_version < 3.24.0`. (Owner: Quinn)
5. **Atualizar CI**: adicionar passo em `.github/workflows/ci.yml` / `.github/workflows/acceptance.yml` para:
   - imprimir `python -c "import sqlite3; print(sqlite3.sqlite_version)"` e falhar/skip ao rodar testes de concorrência se versão < 3.24.0;
   - garantir acceptance job roda com file-backed test (use runner tmp dir). (Owner: Quinn)
6. **Edge-cases & docs**: documentar mudança em `docs/implementation-artifacts/` sobre comportamento do upsert (`INSERT OR REPLACE`) e recomendação de histórico (soft-upsert) e registrar a decisão sobre `check_same_thread` (não alterar por padrão). (Owner: Winston + Paige optional)
7. **Run & iterate**: rodar testes localmente e corrigir flakiness; se intermitência persistir, ajustar `busy_timeout` ou mover para `ProcessPoolExecutor`. (Owner: Quinn)

Verification
- Rodar apenas o teste novo:
```bash
poetry run pytest -q tests/test_concurrency_sqlite.py
```
- Rodar suíte completa:
```bash
poetry run pytest -q
```
- No CI, confirmar job imprime `sqlite3.sqlite_version` e que testes de concorrência são executados ou marcados como skip/xfail quando versão insuficiente.

Decisions (propostas)
- Usar `PRAGMA journal_mode=WAL` e `PRAGMA busy_timeout=30000` como padrão best-effort para conexões de arquivo.
- Não alterar `check_same_thread` globalmente; exigir que cada thread/processo abra sua própria conexão.
- Testes de concorrência devem usar DB file em `tmp_path` (não `:memory:`), e devem pular/xfail quando `sqlite3.sqlite_version < 3.24.0` no runner.

Riscos / Blockers
- Código usa stdlib `sqlite3` (não SQLAlchemy) — aplicar PRAGMAs diretamente em `_connect()`; se o projeto migrar para SQLAlchemy mais tarde, adaptar para `event.listen(engine,'connect',...)`.
- Muitos testes atuais usam `:memory:`; CI/runner SQLite pode não suportar WAL ou versão mínima — precisamos adicionar checagem de versão no CI.

Próximo passo
- Autorizam que eu gere um PR com as mudanças propostas (uma alteração em `src/db.py`, novo `tests/test_concurrency_sqlite.py` e pequena atualização de workflow)? Se sim, eu preparo o diff e os testes.

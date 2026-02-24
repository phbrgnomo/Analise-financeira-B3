---
title: "Plano de Implementação — Integração DB e Pipeline (Story 1.6)"
date: 2026-02-23
story: 1-6-persistir-dados-canonicos-no-sqlite-com-upsert-por-ticker-date
status: draft
---

Objetivo
-
Integrar automaticamente o fluxo de ingestão para persistir linhas canônicas no banco SQLite (`dados/data.db`), harmonizar metadados e ingest_logs (JSONL), consolidar operações de DB em `src/db.py` e adicionar teste de integração fim-a-fim.

Escopo
-
- Chamar `db.write_prices()` automaticamente no pipeline/CLI após `to_canonical()` e validação.
- Manter `ingest_logs` como JSONL append-only em `metadata/ingest_logs.jsonl` (source-of-record para auditoria).
- Consolidar inicialização/DDL do DB em `src/db.py` e transformar `scripts/init_ingest_db.py` em wrapper que delega a `src.db.init_db()`.
- Harmonizar uso de `DATA_DIR` em `src/db.py` (`from src.paths import DATA_DIR`).
- Adicionar teste de integração: `save_raw_csv` → `to_canonical` → `write_prices` → `read_prices`.

Passos de Implementação
-
1) Integração automática (código)
   - Arquivo alvo: `src/main.py`
   - Após `canonical = to_canonical(...)` e validação bem-sucedida, adicionar:
     ```py
     from src import db
     db.write_prices(canonical, f"{a}.SA")
     ```
   - Permitir passar `db_path`/`conn` via flags ou env quando necessário (opcional).

2) Consolidar operações DB (código)
   - Arquivo alvo: `src/db.py` (expandir)
     - Adicionar `init_db(db_path: Optional[str]=None)` que cria/atualiza tabelas (`prices`, `returns`, `snapshots`, `metadata`, `ingest_logs` se decidirmos recriar) de forma idempotente.
     - Expor helpers: `write_prices`, `read_prices`, `record_snapshot_metadata`.
   - Atualizar `scripts/init_ingest_db.py` para chamar `src.db.init_db(resolved)` e manter interface CLI.

3) Ingest logs em JSONL (pipeline)
   - Arquivo alvo: `src/ingest/pipeline.py::save_raw_csv`
   - Em vez de manter apenas `metadata/ingest_logs.json` (array), gravar append por linha em `metadata/ingest_logs.jsonl` com um objeto JSON por ingest.
   - Garantir atomicidade (escrever linha em arquivo aberto com flush + os.fsync) ou usar rename temporário quando necessário.
   - `save_raw_csv` deve retornar o mesmo `metadata` dict (incluindo `raw_checksum`, `fetched_at`, `filepath`).

4) Harmonizar `DATA_DIR` em `src/db.py` (paths)
   - Substituir `os.getcwd()` ou paths relativos por `from src.paths import DATA_DIR` e usar `DATA_DIR / "data.db"` como padrão.
   - Atualizar comentários e documentação.

5) Metadados: JSONL + DB summaries
   - Regra: ingest_logs → JSONL (primary); DB armazena apenas `schema_version` e metadados de schema (snapshots), via `record_snapshot_metadata()` quando aplicável.
   - Implementar `src/db.py::record_snapshot_metadata(metadata: dict)` que grava resumo em tabela `metadata` ou `snapshots`.

6) Teste de integração (tests)
   - Criar: `tests/integration/test_pipeline_db_integration.py`
   - Fluxo do teste (usar fixtures `tmp_path`):
     - Chamar `save_raw_csv(df, provider, ticker, ts, raw_root=tmp, metadata_path=tmp/ingest_logs.jsonl)`
     - Chamar `to_canonical(...)` com os valores retornados por `save_raw_csv`
     - Configurar `db_path = tmp / 'dados' / 'data.db'`; chamar `db.init_db(db_path)` ou garantir `_ensure_schema` antes de `write_prices`
     - Chamar `db.write_prices(canonical, ticker, db_path=str(db_path))`
     - Ler `db.read_prices(ticker, conn=...)` e validar número de linhas, colunas `source` e `raw_checksum` e intervalo `start/end`.
     - Verificar que `tmp/metadata/ingest_logs.jsonl` contém registro do ingest (parse JSONL e verificar `raw_checksum`).
   - Reusar/ajustar fixtures existentes em `tests/conftest.py` quando possível.

7) Documentação
   - Atualizar `docs/sprint-reports/2026-02-23-story-1-6-db-upsert.md` com nota sobre integração automática e JSONL.
   - Atualizar `docs/playbooks/quickstart-ticker.md` com passo de inicialização do DB (`python scripts/init_ingest_db.py`) e observação sobre `ingest_logs.jsonl`.

8) Lint/CI/Commit
   - Rodar `pre-commit` e `poetry run pytest -q` localmente.
   - Criar branch `story-1-6/integration-db`, commitar e abrir PR com descrição e checklist.

Critérios de Aceitação
-
- O fluxo CLI/pipeline grava as linhas canônicas no DB automaticamente quando executado com sucesso.
- `ingest_logs.jsonl` contém um registro por ingest e é gerado independentemente do DB.
- `db.read_prices` retorna corretamente intervalos e metadados (source, raw_checksum).
- Teste de integração fim-a-fim passa em CI.

Riscos e Observações
-
- Fallback `INSERT OR REPLACE` no SQLite causa substituição inteira da linha — documentado e mitigado recomendando SQLite >= 3.24 no CI.
- Decidir se `ingest_logs` também devem ser persistidos em DB (opcional) — recomenda-se manter JSONL como source-of-record para tolerância a falhas.

Próximo passo sugerido
-
Se aprovado, vou criar a branch `story-1-6/integration-db` e implementar os passos 1, 3, 4 e 6 (integração, JSONL, harmonização de paths, teste de integração), rodar testes e abrir PR.

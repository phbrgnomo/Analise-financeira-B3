Plan: Melhorias Story 1.7 (Upsert, testes, docs, infra)

TL;DR

Corrigir a operação de upsert para ser atômica e segura em runtimes antigos, endurecer testes (bordas, concorrência, preservação de metadados), entregar docs e notebook consumidor, refatorar persistência para um adapter DB injetável, adicionar migrações, utilitários de tempo, CI/pre-commit e observabilidade. Isso reduz risco operacional e facilita rollout para consumidores (notebooks/modelagem).

INSTRUCOES:

- rastreie a execução utilizando #tool:todo
- verifique a estrutura do codiog usando #tool:sehejjain.lsp-mcp-bridge/*

Steps

1. Corrigir upsert transacional (alta)
   - Implementar padrão UPDATE→INSERT ou transação atômica em `src/db.py`.
   - Evitar comportamento destrutivo de `INSERT OR REPLACE` quando possível.
   - Adicionar logging e rollback em erro.

2. Adicionar testes críticos (alta)
   - `test_write_returns_preserves_created_at_when_upsert_supported`.
   - `test_compute_returns_handles_gaps` (NaN, feriados, datas faltantes).
   - `test_compute_returns_empty_prices` e `test_compute_returns_single_price`.
   - Simular fallback de versão SQLite (mock) e concorrência (threads/processos).

3. Docs & notebook (alta)
   - Criar `docs/examples/notebooks/returns-consumer.ipynb` com quickstart.
   - Atualizar `docs/implementation-artifacts/retornos-conventions.md` com exemplos SQL, nota de compatibilidade SQLite e checklist de validação para consumidores.

4. Refatorar para adapter DB (média-alta)
   - Introduzir `DatabaseClient`/repo interface (`src/db/client.py`).
   - Ajustar `compute_returns()` em `src/retorno.py` para aceitar `repo` injetado.
   - Atualizar fixtures/tests para injetar fakes.

5. Migrations (média)
   - Criar `migrations/` com scripts numerados e runner simples.
   - Declarar `returns` no schema canônico (`docs/schema.json`) e integrar em `init_db()`.

6. Time utils (média)
   - Adicionar `src/time_utils.py` com `now_utc_iso()` e parsers.
   - Substituir usos ad-hoc de datetime em `src/retorno.py` e `src/db.py`.

7. CI / testes (média)
   - Separar jobs `unit` / `integration` / `e2e` no CI.
   - Bloquear merge se unit+contract falharem; rodar integration/e2e em runners dedicados.
   - Bloquear rede em testes (mock `yfinance`/adapters) e usar DB efêmero por teste.

8. Pre-commit + linters (baixa-média)
   - Documentar fluxo local (poetry, pre-commit install).

9. Observabilidade (baixa-média)
   - Instrumentar métricas básicas (rows_written, duration_ms, failures).
   - Centralizar logs estruturados e expor pontos para integração futura (Prometheus/Influx).

10. Checklist (baixa)
   - Incluir checklist de revisão exigindo testes, docs, migrations e nota sobre SQLite.

Verification

- Unit & integration tests: rodar `poetry run pytest -q` (usar marcação para integration). Garantir pipeline verde.
- Testes manuais:

```bash
poetry run python -m src.main compute-returns --ticker PETR4.SA --dry-run
poetry run python -m src.main compute-returns --ticker PETR4.SA
sqlite3 dados/data.db "SELECT ticker, date, return, created_at FROM returns WHERE ticker='PETR4.SA' ORDER BY date LIMIT 5;"
```

- Verificar que `created_at` não mudou após re-run (quando `ON CONFLICT` suportado).

Decisions

- Priorizar correção do upsert e cobertura de testes antes de refactor grande (adapter).
- Fail-fast: se runtime SQLite < 3.24.0 e fallback não puder preservar metadados, CLI deve avisar/recusar execução em ambientes críticos até a migração ser planeada.

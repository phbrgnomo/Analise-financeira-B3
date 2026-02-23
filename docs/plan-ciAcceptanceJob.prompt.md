# Plan: CI Acceptance Workflow

TL;DR — Criar `.github/workflows/acceptance.yml` que executa um job matrix (`ubuntu-latest`, Python 3.12) para: instalar dependências (Poetry), inicializar DB, gerar snapshots determinísticos em `$RUNNER_TEMP/snapshots_test` (usando `examples/run_quickstart_example.sh` ou `scripts/run_save_raw_example.py`), validar checksums com `scripts/validate_snapshots.py` e rodar o teste E2E crítico. Opcionalmente adicionar `scripts/verify_snapshot.py` e um teste E2E reproduzível para facilitar manutenção.

**Steps**
1. **Criar workflow:** adicionar [.github/workflows/acceptance.yml](.github/workflows/acceptance.yml) — job matrix (ubuntu / py3.12) com passos: checkout → setup-python → cache/instalar poetry → init DB → gerar snapshots em `$RUNNER_TEMP/snapshots_test` → validar checksums → rodar pytest E2E → upload artifacts (snapshots_test, reports) em falha.
2. **Usar gerador existente:** executar `examples/run_quickstart_example.sh` ou `python scripts/run_save_raw_example.py` apontando `SNAPSHOT_DIR=$RUNNER_TEMP/snapshots_test` para gerar snapshots determinísticos no runner.
3. **Validar checksums:** usar [scripts/validate_snapshots.py](scripts/validate_snapshots.py) para comparar contra `snapshots/checksums.json`; falha deve retornar non-zero para quebrar o job.
4. **Adicionar wrapper CLI (opcional):** criar [scripts/verify_snapshot.py](scripts/verify_snapshot.py) — pequeno wrapper que chama `validate_snapshots.py` e expõe flags simples (`--dir`, `--manifest`, exit codes claros) para clareza no workflow.
5. **Adicionar teste E2E (opcional):** adicionar `tests/e2e/test_acceptance_snapshot.py` que reproduz o fluxo (gera snapshot em `tmp_path` e valida com `scripts/validate_snapshots.py`) para permitir execução local via `pytest`.
6. **Documentar:** adicionar `docs/quickstart-ci.md` com comandos exatos para reproduzir localmente (poetry install, init db, run quickstart, validate).
7. **PR & Monitor:** criar branch/PR com mudanças e acompanhar runs do workflow; iterar até green.

**Verification**
- Comandos locais para validar o fluxo end-to-end:
```bash
# 1) Instalar deps
poetry install

# 2) Inicializar DB (opcional)
python scripts/init_ingest_db.py --db dados/data.db

# 3) Gerar snapshot em dir temporária
mkdir -p ./snapshots_test
SNAPSHOT_DIR=$PWD/snapshots_test ./examples/run_quickstart_example.sh
# ou
SNAPSHOT_DIR=$PWD/snapshots_test python scripts/run_save_raw_example.py --out-dir snapshots_test

# 4) Validar checksums
python scripts/validate_snapshots.py --dir snapshots_test --manifest snapshots/checksums.json

# 5) Rodar teste E2E crítico
poetry run pytest -q tests/test_integration_e2e_checksum.py
```

**Decisions (recomendadas)**
- **Trigger:** rodar em PRs apenas se arquivos relevantes mudarem (`paths:` on push/pull_request para `src/**`, `snapshots/**`, `tests/**`, `.github/workflows/**`).
- **Network mode:** usar `NETWORK_MODE=playback` em CI para determinismo; habilitar `record` só em jobs controlados/manual.
- **Failure semantics:** qualquer mismatch no `validate_snapshots.py` deve retornar exit code !=0 para marcar job como failed; upload de `snapshots_test` e `reports/junit.xml` sempre em falha.
- **Optional:** adicionar `scripts/verify_snapshot.py` e teste E2E para facilitar debug e garantir paridade local/CI.

**Arquivos a criar/alterar**
- Add: [.github/workflows/acceptance.yml](.github/workflows/acceptance.yml)
- Add: [scripts/verify_snapshot.py](scripts/verify_snapshot.py)
- Add: [tests/e2e/test_acceptance_snapshot.py](tests/e2e/test_acceptance_snapshot.py)
- Add: [docs/quickstart-ci.md](docs/quickstart-ci.md)

**Próximos passos (rúbrica de execução)**
- Incorporar testes adicionados no scritp `ci_orchestrator.py` para rodar o workflow localmente.
- Rodar os testes localmente para garantir que o fluxo é reproduzível.
- Commitar as mudanças no branch atual

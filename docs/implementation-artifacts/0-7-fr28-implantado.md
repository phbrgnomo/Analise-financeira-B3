# FR28 — Documentação do que foi implantado (Story 0.7)

Resumo das implementações realizadas para atender o FR28 relacionadas à Story 0.7

Status geral: in-review

Implementações e evidências
- Teste de integração mockado: `tests/integration/test_quickstart_mocked.py` (2 tests).
  - Evidência: commit `29a1fd9`.
- Fixture `snapshot_dir` disponível globalmente: `tests/conftest.py` (respeita `SNAPSHOT_DIR`).
  - Evidência: commit `26cb06f`.
- Utilitário de checksum SHA256: `src/utils/checksums.py`.
  - Usado pelo teste para validar `.checksum`.
- CI: Job `integration` em `.github/workflows/ci.yml` ajustado para definir `SNAPSHOT_DIR=snapshots_test` e fazer upload de `snapshots_test/**`.
  - Evidência: commit `26cb06f`.
- Fixture de referência de checksum: `tests/fixtures/expected_snapshot.checksum` (valor de referência incluído).

Resultados dos testes (local)
- Suíte completa: `6 passed, 10 warnings` (execução local).
- Testes de integração: `2 passed`.

Como verificar localmente
1. Instalar dependências e rodar todos os testes:
```bash
poetry install
poetry run pytest -q
```
2. Rodar apenas testes de integração:
```bash
poetry run pytest -q tests/integration -k quickstart_mocked
```
3. Para simular CI artifacts localmente, exporte `SNAPSHOT_DIR` antes de rodar:
```bash
export SNAPSHOT_DIR=snapshots_test
poetry run pytest -q tests/integration -k quickstart_mocked
ls -la snapshots_test
```

Notas/Próximos passos
- Abrir PR e executar CI remoto para validar upload de artifacts e comportamento em runner.
- Atualizar `docs/planning-artifacts/prd.md` apenas se for necessário alteração de requisitos; esta documentação descreve o que foi implantado para rastreabilidade conforme FR28.

Arquivos principais alterados/gerados
- `tests/integration/test_quickstart_mocked.py`
- `tests/conftest.py` (fixture `snapshot_dir`)
- `tests/ci/conftest.py` (compatibilidade com `SNAPSHOT_DIR`)
- `src/utils/checksums.py`
- `.github/workflows/ci.yml`

Issue de referência: https://github.com/phbrgnomo/Analise-financeira-B3/issues/110

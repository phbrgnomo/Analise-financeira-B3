# FR28 — Documentação do que foi implantado (Story 0.7)

Resumo das implementações realizadas para atender ao FR28, relacionadas à Story 0.7.

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

---

## Relatório de Sprint — Story 0.7 (integração mocked + CI checksum)

Objetivo do sprint
- Implementar um teste de integração _quickstart_ que rode de forma mockada (sem rede) e gere um snapshot CSV acompanhado de `.checksum` SHA256.
- Fazer com que o pipeline de CI execute esse teste e publique os artifacts resultantes para inspeção manual.

Por que isso importa
- Garante reprodutibilidade do quickstart em CI sem depender de provedores externos, reduzindo flakiness e tempo de execução.
- Introduz verificação automática de integridade via checksum que pode prevenir regressões silenciosas na geração de snapshots.

Mapping para Acceptance Criteria (AC)
- AC1: Geração de snapshot CSV em ambiente CI com fixtures/provedores mockados → IMPLEMENTADO (teste `tests/integration/test_quickstart_mocked.py`)
- AC2: Cálculo de checksum SHA256 e comparação com valor esperado → IMPLEMENTADO (utilitário `src/utils/checksums.py` + fixture `tests/fixtures/expected_snapshot.checksum`)
- AC3: Publicação do CSV e `.checksum` como artefato → PARTIAL (CI configured to upload `snapshots_test/**`; requires remote CI run to validate upload)
- AC4: Workflow CI definido em `.github/workflows/ci.yml` e inclui etapa de integração mockada + validação → IMPLEMENTADO (job `integration` updated to set `SNAPSHOT_DIR`)

O que foi implementado (detalhado)
- Testes
  - `tests/integration/test_quickstart_mocked.py` — teste de integração com dois casos: geração do snapshot + verificação do diretório temporário.
  - Uso de monkeypatch para simular o wrapper `web.DataReader`/`yfinance` evitando rede.
- Fixtures
  - `tests/conftest.py` — adição de fixture `snapshot_dir` (escopo session) que respeita `SNAPSHOT_DIR` quando setado (CI friendly).
  - `tests/ci/conftest.py` — compatibilidade adicional para runners/legacy.
- Utilitários
  - `src/utils/checksums.py` — funções `sha256_file` e `sha256_bytes` usadas para validação.
- CI
  - `.github/workflows/ci.yml` — job `integration` atualizado com `env: SNAPSHOT_DIR: snapshots_test` e upload de `snapshots_test/**`.
- Documentação
  - `docs/implementation-artifacts/0-7-fr28-implantado.md` — documento FR28 (implantado) criado
  - `docs/implementation-artifacts/0-7-teste-de-integracao-quickstart-mocked-e-passo-de-ci-para-validacao-de-checksum.md` — story atualizada (status `in-review`, file list atualizado)

Evidências (commits / arquivos)
- Commits relevantes:
  - `29a1fd9` — add quickstart_mocked integration test
  - `26cb06f` — add mocked quickstart test; respect SNAPSHOT_DIR fixture; set SNAPSHOT_DIR in CI; update story File List
  - `7261e68` — docs update for story status and completion notes
  - `6e92f78` — FR28 doc created
- Arquivos chave:
  - `tests/integration/test_quickstart_mocked.py`
  - `tests/conftest.py` and `tests/ci/conftest.py`
  - `src/utils/checksums.py`
  - `.github/workflows/ci.yml`
  - `tests/fixtures/expected_snapshot.checksum`

Como verificar (passo a passo)
1. Local (rápido):
```bash
poetry install
poetry run pytest -q tests/integration -k quickstart_mocked
```
2. Local (full):
```bash
poetry run pytest -q
```
3. Simular CI artifact collection localmente:
```bash
export SNAPSHOT_DIR=snapshots_test
poetry run pytest -q tests/integration -k quickstart_mocked
ls -la snapshots_test
```
4. PR / CI: abrir PR da branch `epic-0` para `master` e verificar job `integration` gera artifacts no run do GitHub Actions.

Decisões técnicas e justificativas
- Usar monkeypatch no wrapper `web.DataReader`/`yfinance` simplifica a simulação de fontes e mantém compatibilidade com o código existente (`src.dados_b3`).
- Centralizar fixture `snapshot_dir` em `tests/conftest.py` (escopo global) permite reuso em testes unitários e de integração e facilita a configuração via `SNAPSHOT_DIR` pelo CI.
- Escolha de SHA256 por ser amplamente suportado e facilmente verificável em runners.

Riscos, limitações e recomendações
- Risco: upload de artifacts precisa ser validado no runner real — confirmar em PR CI run.
- Limitação: teste de integração foi movido para `tests/integration/`; se times/operadores esperam `tests/ci/` o workflow precisará de alinhamento (aceitamos `SNAPSHOT_DIR` env).
- Recomendação: após merge, executar job `integration` manualmente ou abrir PR menor que desencadeie CI para verificar upload.

Lições aprendidas
- Fixtures e paths de artifact devem ser explicitamente coordenados entre testes e workflows CI para evitar artefatos órfãos.
- Pre-commit/linters ajudam a manter padrão de código; ajustes de docstrings e linha-comprimento foram necessários.

Próximos passos (backlog curto)
- Validar CI remoto (abrir PR e confirmar upload de artifacts) — prioridade alta.
- Consolidar orientação de onde localizar testes de integração (`tests/integration` vs `tests/ci`) no README/CONTRIBUTING.
- Documentar runbook breve para recuperação de snapshots/checagem de checksum no ambiente de operações.

Contato
- Autor/implementador: Phbr

---

Arquivo mantido em `docs/sprint-reports/0-7-integracao-implantado.md`

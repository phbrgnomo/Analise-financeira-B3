 # Story 0.7: Teste de integração quickstart (mocked) e passo de CI para validação de checksum

 Status: ready-for-dev

 ## Story

 As a Engenheiro de CI / Desenvolvedor,
 I want um teste de integração mockado que execute o quickstart e um passo de CI que valide checksums de snapshot,
 so that o pipeline de CI valide a geração de snapshot CSV e a integridade dos arquivos sem dependências de rede.

 ## Acceptance Criteria

 1. Dado um ambiente CI com fixtures e provedores mockados, ao rodar o teste de integração quickstart, um snapshot CSV é gerado.
 2. O job de CI calcula o checksum SHA256 do CSV gerado e compara com o valor esperado; o job falha em caso de mismatch.
 3. O CI publica o CSV gerado e um arquivo `.checksum` como artefato para inspeção manual.
 4. O workflow CI está definido em `.github/workflows/ci.yml` e inclui a etapa de integração mockada + validação de checksum.

 ## Tasks / Subtasks

 - [ ] Implementar teste de integração mockado: `tests/integration/test_quickstart_mocked.py`
   - [ ] Criar fixtures (em `tests/fixtures/`) que forneçam dados CSV e respostas de provedor mockadas
   - [ ] Mockar adaptadores de provedores (ex.: monkeypatch / requests-mock) para que `pipeline.ingest` rode sem rede
   - [ ] Validar que `snapshots/<ticker>-*.csv` é criado e contém cabeçalho esperado
 - [ ] Implementar utilitário de checksum em `src/utils/checksums.py` (SHA256)
 - [ ] Atualizar `.github/workflows/ci.yml` para incluir etapa de integração mockada, cálculo de checksum e publicação de artefatos
 - [ ] Adicionar arquivo de referência `tests/fixtures/expected_snapshot.checksum` com valor esperado para o teste
 - [ ] Documentar passo-a-passo em `docs/implantacao/0-7-teste-de-integracao.md`
 - [ ] Documentar o que foi implantado nessa etapa conforme o FR28 (`docs/planning-artifacts/prd.md`)

 ## Dev Notes

 - Use mocks para provedores: não fazer chamadas de rede em CI para garantir robustez e velocidade.
 - Snapshot CSV deve conter metadados (header ou arquivo paralelo) com `created_at`, `rows`, `checksum`.
 - Checksum deve ser SHA256 sobre o conteúdo do CSV gerado (texto raw, sem metadados extras) — documentado e testado.
 - Paths esperados: `snapshots/` para artefatos, `raw/` para raw responses (quando aplicável).
 - Ferramentas recomendadas: `pytest` + `pytest-mock`/`requests-mock`, `pandas` para leitura/validação de CSV.
 - Evitar dependências de rede: usar fixtures em `tests/fixtures/` e usar monkeypatch para adapters.

 ### Project Structure Notes

 - Tests de integração: `tests/integration/test_quickstart_mocked.py`
 - Fixtures: `tests/fixtures/sample_snapshot.csv`, `tests/fixtures/expected_snapshot.checksum`
 - Utilitários: `src/utils/checksums.py`

 ### References

 - Fonte de requisitos: docs/planning-artifacts/epics.md (Story 0.7)
 - PRD: docs/planning-artifacts/prd.md
 - Arquitetura: docs/planning-artifacts/architecture.md

 ## Dev Agent Record

 ### Agent Model Used

 GPT-5 mini (GitHub Copilot)

 ### Completion Notes List

 - Arquivo de story criado com requisitos, critérios de aceite e tarefas iniciais.
 - Sprint-status atualizado para `ready-for-dev`.

 ### File List

 - docs/planning-artifacts/epics.md
 - docs/planning-artifacts/prd.md
 - docs/planning-artifacts/architecture.md
 - tests/integration/test_quickstart_mocked.py
 - tests/ci/conftest.py
 - .github/workflows/ci.yml
 - src/utils/checksums.py

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/110

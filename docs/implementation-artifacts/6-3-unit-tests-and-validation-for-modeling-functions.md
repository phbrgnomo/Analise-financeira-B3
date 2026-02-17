---
generated: 2026-02-17T00:00:00Z
story_key: 6-3-unit-tests-and-validation-for-modeling-functions
epic: 6
story_num: 3
status: ready-for-dev
---

# Story 6.3: unit-tests-and-validation-for-modeling-functions

Status: ready-for-dev

## Story

Como QA/Desenvolvedor,
eu quero testes unitários que validem o comportamento de `portfolio.generate` e seus casos de borda,
para que alterações no código de modelagem não quebrem outputs esperados.

## Acceptance Criteria

1. Dado conjunto determinístico de fixtures em `tests/fixtures/modeling/`, ao rodar `pytest tests/modeling/test_portfolio.py`:
   - Testes validam que os pesos estão normalizados (soma = 1 dentro de tolerância);
   - Testes cobrem comportamento para ativos com volatilidade zero (tratamento definido: atribuir peso mínimo ou fallback determinístico);
   - Testes verificam que entradas idênticas e parâmetros idênticos produzem pesos/ métricas determinísticas dentro de tolerância configurável (ex.: atol=1e-6/rtol=1e-6).
2. Fixtures de teste pequenas e determinísticas são colocadas em `tests/fixtures/modeling/` e documentadas em `tests/fixtures/README.md`.
3. CI inclui um job (ou matriz) que executa `pytest -q` para a suíte de modelagem; falhas bloqueiam merge.

## Tasks / Subtasks

- [ ] Criar `tests/fixtures/modeling/sample_prices.csv` e loader de fixture em `tests/conftest.py` ou `tests/fixtures/__init__.py`.
- [ ] Implementar `tests/modeling/test_portfolio.py` com casos parametrizados:
  - [ ] teste_normalizacao_de_pesos
  - [ ] teste_zero_volatilidade
  - [ ] teste_determinismo_para_inputs_fixos
- [ ] Integrar job de CI (ou validar que CI existente roda `pytest` para o diretório `tests/modeling`).
- [ ] Documentar como executar os testes localmente no `README`/`docs` (comando exemplar: `poetry run pytest tests/modeling -q`).

## Dev Notes

- Local do código de modelagem sugerido: `src/portfolio.py` ou `src/modeling/portfolio.py`.
- Testes devem usar `numpy.testing.assert_allclose` ou `pandas` comparadores com tolerâncias configuráveis.
- Evitar dependência de rede: usar fixtures/fixtures loaders e `--no-network` em CI quando aplicável.
- Seed determinístico (e.g., `np.random.seed(42)`) em testes que usam aleatoriedade; prefer deterministic algorithms for production code.

### Project Structure Notes

- Fixtures: `tests/fixtures/modeling/` (CSV(s) + README)
- Tests: `tests/modeling/test_portfolio.py`
- Implementation suggestion: `src/portfolio.py` → função `portfolio.generate(prices_df, params)` deve ser importável e testável sem efeitos colaterais.

### References

- Fonte: [docs/planning-artifacts/epics.md](docs/planning-artifacts/epics.md#epic-6-—-modelagem-de-portfólio)
- Sprint tracking: docs/implementation-artifacts/sprint-status.yaml

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Completion Notes List

- Arquivo de história criado e marcado como `ready-for-dev`.

### File List

- tests/fixtures/modeling/ (sugerido)
- tests/modeling/test_portfolio.py (sugerido)

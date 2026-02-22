---
generated: 2026-02-17T00:00:00Z
story_key: 6-1-implementar-portfolio-generate-poc
epic: 6
story_num: 1
status: ready-for-dev
owner: Phbr
---

# Story 6.1: Implementar portfolio.generate POC

Status: ready-for-dev

## Story

As a Researcher/Developer,
I want a minimal `portfolio.generate(prices_df, params)` implementation that returns asset weights and summary metrics,
so that I can produce reproducible portfolio allocation POCs and verify end-to-end integration with notebooks.

## Acceptance Criteria

1. Dado `prices` canônicos ou `returns` para um conjunto de tickers, ao executar `portfolio.generate(prices_df, params)`:
   - Retorna um objeto com `weights` (mapa ticker->peso), `expected_return`, `volatility`, `sharpe` e `run_id` identificável.
   - Aceita parâmetros: `risk_target`, `method` (`equal` | `mean-variance`), `lookback_days`.
   - É determinístico para os mesmos inputs e params (mesmo `run_id` apenas se solicitado / ou gerado por hash dos inputs).
2. Sumarização e exportação mínima suportada para CSV/JSON pela story 6.2.
3. Comportamento documentado e testável via fixtures em `tests/fixtures/modeling/` (ver story 6.3).

## Tasks / Subtasks

- [ ] Implementar função `portfolio.generate(prices_df, params)` em `src/modeling/portfolio.py` (POC simples).
  - [ ] Método `equal`: normaliza pesos iguais por ativo.
  - [ ] Método `mean-variance`: calcular retornos esperados, matriz de covariância, resolver otimização quadrática simples (cvxopt optional) ou fallback heurístico.
  - [ ] Gerar `run_id` (UUID ou hash dos inputs + params) e incluir `created_at`.
- [ ] Implementar CLI wrapper `pipeline.model --tickers <list> --method <method> --out <path>` em `src/cli.py` (ou extensão de `main`).
- [ ] Adicionar export routine CSV/JSON (story 6.2) que escreve `results/portfolio-<run_id>.csv` e `results/portfolio-<run_id>.json`.
- [ ] Criar fixtures de unit test em `tests/fixtures/modeling/` e testes em `tests/modeling/test_portfolio.py` (story 6.3).
- [ ] Documentar uso e parâmetros em `docs/playbooks/modeling-quickstart.md`.

## Dev Notes

- Localização sugerida de código:
  - `src/modeling/portfolio.py` — implementação principal do POC
  - `src/cli.py` ou `src/main.py` — adicionar comando `pipeline.model`
  - `results/` — diretório para outputs de modelagem (CSV/JSON)
  - `tests/fixtures/modeling/` — fixtures determinísticas para CI

- Dependências e escolhas técnicas (POC):
  - Preferir soluções em-core com `numpy`/`pandas` e `scipy` se disponível; evitar dependências pesadas (ex.: `cvxpy`) no POC salvo justificativa.
  - Determinismo: definir random seed quando for usar amostragens.

- Testes:
  - Validar que `weights` somam ~1.0 (dentro de tolerance 1e-6).
  - Casos borda: ativos com volatilidade zero, único ativo, lookback mais curto que `prices_df`.

### Project Structure Notes

- Alinhar nomes de módulos com convenção existente em `src/`.
- Evitar alterações em interfaces públicas sem documentação de migração.

### References

- Source: docs/planning-artifacts/epics.md#Epic-6—Modelagem-de-Portfólio
- Source: docs/planning-artifacts/epics.md (FR24, FR25)

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Debug Log References

### Completion Notes List

### File List

- src/modeling/portfolio.py (proposto)
- src/cli.py (extensão proposta)
- results/portfolio-<run_id>.csv


Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/149

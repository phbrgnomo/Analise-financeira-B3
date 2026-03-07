---
generated: 2026-02-17T00:00:00Z
story_key: 6-6-documentacao-e-exemplos-de-uso-para-modelagem
epic: 6
story: 6.6
status: ready-for-dev
---

# Story 6.6: Documentação e exemplos de uso para modelagem

Status: ready-for-dev

## Story

As a Tech Writer/Developer,
I want a short `docs/modeling.md` with usage examples, expected inputs and outputs, and recommended parameter presets,
so that contributors can run the model and understand typical results.

## Acceptance Criteria

1. Copy-paste commands for running model via CLI (`poetry run main --model --tickers ... --method mean-variance`) are present.
2. Expected input format and example inputs (returns/prices DataFrame schema) are documented.
3. Example outputs (CSV/JSON snippets) and companion `.checksum` generation instructions are provided.
4. Troubleshooting notes covering data-quality and lookback choices are included.
5. Recommended parameter presets for common scenarios (small POC, research, production-sim) are listed.

## Tasks / Subtasks

- [ ] Create `docs/modeling.md` with sections: Overview, Quickstart, Inputs, Outputs, Examples, Troubleshooting, Presets
- [ ] Add example CLI commands and expected sample output snippets
- [ ] Add sample CSV/JSON output files or examples under `docs/examples/modeling/` (inline snippets acceptable)
- [ ] Cross-link to `notebooks/modeling_example.ipynb` and `tests/fixtures/modeling/` (if present)
- [ ] Update `README.md` quickstart with one modeling example line
- [ ] Peer review docs with owner (Phbr) and merge to main

## Dev Notes

- Source material: docs/planning-artifacts/epics.md (Epic 6, Story 6.6)
- Expected inputs: canonical `prices` or `returns` DataFrame with columns that follow `docs/schema.json` (e.g.: `ticker`, `date`, `open`, `high`, `low`, `close`, `volume`).
  Note: `adj_close` may be emitted by the mapper for internal calculations (e.g., returns), but it is not persisted by default — update `docs/schema.json` to persist it if needed.
- Recommended implementation location: `src/modeling.py` (function `portfolio.generate(prices_df, params)`) and a thin CLI wrapper in `src/main.py` (`--model`) to call it.
- Example output locations: `results/portfolio-<run_id>.csv` and `results/portfolio-<run_id>.json` with companion `<run_id>.checksum` (SHA256 of CSV)
- Minimal library recommendations: `numpy`, `pandas`, `scipy` (optional), keep dependencies minimal; prefer deterministic RNG seed handling if any stochastic methods used

### Project Structure Notes

- Suggested file additions:
  - `src/modeling.py` — `portfolio.generate` POC
  - `docs/modeling.md` — this document (final)
  - `docs/examples/modeling/` — small examples (optional)
  - `tests/modeling/test_portfolio.py` — unit tests verifying deterministic behavior

### Architecture / Compliance Notes

- Comply with existing project conventions: 252 trading days for annualization, use `dados/data.db` as canonical DB when demonstrating end-to-end runs, avoid adding heavy runtime deps unless justified.
- Prefer pure-Python deterministic implementations for POC (no GPU/compiled libs). Document any non-standard requirements.

### Testing Requirements

- Provide at least one unit test using fixture data under `tests/fixtures/modeling/` that validates:
  - weights sum to 1
  - behavior for zero-volatility asset(s)
  - deterministic output for fixed seed and inputs

### References

- Source: docs/planning-artifacts/epics.md#Epic-6 — Modelagem de Portfólio (sections for Story 6.6)

## Dev Agent Record

### Agent Model Used

Automated BMad agent (agent execution record)

### Completion Notes List

- Created story document and marked story as `ready-for-dev` in sprint-status.yaml

### File List

- docs/implementation-artifacts/6-6-documentacao-e-exemplos-de-uso-para-modelagem.md

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/154

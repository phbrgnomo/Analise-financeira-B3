---
story_key: 6-2-exportar-resultados-de-modelagem-em-csv-json
epic: 6
story_num: 2
status: ready-for-dev
generated_by: automated-create-story
---

# Story 6.2: Exportar resultados de modelagem em CSV/JSON

Status: ready-for-dev

## Story

As a Desenvolvedor/Analista,
I want exportar os resultados de modelagem (pesos, métricas, parâmetros) em formatos CSV e JSON,
so that notebooks e consumidores downstream possam ingerir e analisar os resultados de forma reprodutível.

## Acceptance Criteria

1. O sistema produz um arquivo CSV e/ou JSON contendo: `ticker`, `run_id`, `model`, `params`, `weights` (se aplicável), `expected_return`, `volatility`, `sharpe`, `created_at`.
2. Os arquivos são salvos em `snapshots/modeling/` ou `snapshots/<ticker>/modeling/` com padrão de nome `<ticker>-modeling-YYYYMMDDTHHMMSSZ.(csv|json)` e um arquivo `.checksum` com SHA256 do payload.
3. Existe um contrato programático: `portfolio.export_results(result: dict, path: Path, format: 'csv'|'json') -> Path` documentado e testado.
4. CLI: `poetry run main export-model --ticker <TICKER> --run-id <RUN_ID> --format csv|json --out <path>` que retorna código de saída 0 e imprime o caminho do arquivo gerado.
5. Unit+integration tests que validam schema dos arquivos, conteúdo básico (campos obrigatórios) e checksum gerado.
6. Metadata adicional (model_params, sampling_window, seed) é incluída no JSON e como comentário/arquivo companion quando aplicável.

## Tasks / Subtasks

- [ ] Definir schema de export (CSV columns + JSON structure) — Owner: Dev
  - [ ] Exemplo de JSON/CSV e documentação em `docs/` (adapter-mappings/outputs)
- [ ] Implementar `src/modeling/exporter.py` com `export_results()` (CSV/JSON) e `compute_checksum()` utilitário — Owner: Dev
- [ ] Integrar comando CLI `export-model` em `src/main.py`/`src/cli.py` — Owner: Dev
- [ ] Adicionar testes: `tests/test_exporter.py` (unit) e `tests/test_cli_export.py` (integration mocked) — Owner: QA/Dev
- [ ] Atualizar `docs/playbooks/quickstart-ticker.md` com exemplo de uso e sample outputs — Owner: Tech Writer
- [ ] CI: adicionar step que gera export mocked e valida checksum (.checksum) — Owner: Dev/CI

## Dev Notes

- Preferir `pandas.DataFrame` → CSV usando `to_csv(index=False)` com columns ordenadas pelo schema.
- JSON: usar `orjson` se disponível para performance; fallback para `json` builtin. Incluir `ensure_ascii=False` e ISO8601 UTC para timestamps.
- Gerar `run_id` (UUID4) quando não fornecido; incluir em metadados e no nome do arquivo.
- Calcular SHA256 do conteúdo canônico (sem metadados companion) e gravar em `<file>.checksum` com formato hex.
- Gravar arquivos com permissões padrão do repositório; para dados sensíveis, documentar política em `docs/`.

### Schema CSV (colunas mínimas)

- ticker, run_id, model, params, weights, expected_return, volatility, sharpe, created_at

### Exemplo JSON (resumo)

{
  "ticker": "PETR4.SA",
  "run_id": "...",
  "model": "markowitz",
  "params": {"window": 252, "method": "eq_weight"},
  "weights": {"PETR4.SA": 0.5, "VALE3.SA": 0.5},
  "expected_return": 0.12,
  "volatility": 0.18,
  "sharpe": 0.67,
  "created_at": "2026-02-17T00:00:00Z"
}

## Project Structure Notes

- Implementação sugerida: `src/modeling/exporter.py`, CLI entry `src/cli.py` → comando `export-model`.
- Local de saída padrão: `snapshots/modeling/` ou `snapshots/<ticker>/modeling/`.

## References

- Source: docs/planning-artifacts/epics.md (FR25, FR24)
- Source: docs/planning-artifacts/prd.md (Exportação e contratos de `portfolio.generate`, seções "Modelagem & Portfólio")
- Architecture guidance: docs/planning-artifacts/architecture.md (seções: Snapshot Manager / Exporter, Implementation Patterns)

## Dev Agent Record

### Agent Model Used

automated-agent

### Completion Notes List

- Ultimate context engine analysis completed for story 6-2.

### File List

- docs/implementation-artifacts/6-2-exportar-resultados-de-modelagem-em-csv-json.md

---

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/150

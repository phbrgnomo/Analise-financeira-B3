---
generated: 2026-02-17T00:00:00Z
epic: 6
story: 6.5
key: 6-5-performance-and-smoke-metrics-for-model-runs
status: ready-for-dev
owner: TBD
---

# Story 6.5: Performance e métricas smoke para execuções de modelo

Status: ready-for-dev

## Story

Como Operador/Desenvolvedor,
quero métricas básicas de execução de modelos (tempo, memória, linhas processadas),
para que possamos definir expectativas para testes smoke em CI e runs locais.

## Acceptance Criteria

1. Dado um run de modelo sobre dados de fixture,
   quando a execução completar,
   então deve ser emitido um resumo JSON pequeno contendo as chaves: `run_id`, `elapsed_sec`, `rows_used`, `peak_memory_mb`.
2. O comando/funcionalidade de modelagem deve suportar `--format json` para saída de resumo quando solicitado.
3. As métricas devem ser compatíveis com execução em CI (baixo overhead) e serem fáceis de assertar em testes automatizados.

## Tasks / Subtasks

- [ ] Implementar função utilitária para medir elapsed time e peak memory durante execução do modelo
  - [ ] Definir e documentar API: `with measure_run_context(run_id) -> context` ou `measure_and_run(func, *args, **kwargs)`
- [ ] Emitir resumo JSON ao finalizar com o schema definido abaixo
- [ ] Adicionar opção CLI `--format json` no subcomando de modelagem (ex.: `pipeline.model` ou `main --model ...`)
- [ ] Adicionar testes unitários e de integração (fixture) que validam keys e formatos
- [ ] Documentar em `docs/modeling.md` e referenciar em README quickstart

## Dev Notes

- Output JSON summary schema (exemplo):

```json
{
  "run_id": "str",
  "elapsed_sec": 0.123,
  "rows_used": 100,
  "peak_memory_mb": 45.6
}
```

- Measurement guidance:
  - `elapsed_sec`: wall-clock seconds (float, 3 decimal places)
  - `rows_used`: número de linhas de entrada usadas pelo modelo (inteiro)
  - `peak_memory_mb`: memória máxima observada durante run (MB, arredondar 1 decimais)
  - `run_id`: UUID4 ou hash determinístico (incluir timestamp UTC)

- Implementation hints:
  - Use `time.perf_counter()` para alta resolução de tempo
  - Para peak memory em Linux/CI, preferir `psutil.Process().memory_info().rss` polled durante run, ou `tracemalloc` para memória Python específica. Evitar heavy instrumentation que altere performance.
  - Fornecer uma opção de polling low-overhead (ex.: amostragem a cada 0.1s configurável) ou usar a menor sobrecarga possível em CI
  - Emitir JSON summary tanto para stdout quando `--format json` for usado, e também gravar em `outputs/model_runs/<run_id>.json` como artefato opcional

### Project Structure Notes

- Recomenda-se implementar utilitário em `src/telemetry.py` ou `src/modeling/telemetry.py` e importar no módulo de modelagem.
- CLI: adicionar flag `--format` em `src/main.py` (Typer) ou no handler do subcomando `pipeline.model`.
- Artefatos: gravar sumário em `outputs/model_runs/` e garantir permissões padrão do repositório.

### Testing Notes

- Unit tests:
  - `tests/modeling/test_metrics.py` deve mockar fixtures (pequeno DataFrame) e verificar que o JSON contém as chaves esperadas e formatos numéricos.
  - Test de tolerância: validar que `elapsed_sec` é > 0 e `rows_used` corresponde ao fixture.

- Integration/CI smoke test:
  - Executar `poetry run main --model --tickers PETR4.SA --format json` (ou `pipeline.model`) com fixture data em CI e assertar que `outputs/model_runs/<run_id>.json` existe e contém `peak_memory_mb` numérico.

## Developer Context & Guardrails

- Reuse existing modeling entrypoints: se `portfolio.generate` (Epic 6) já existir, instrumentar ao redor dessa função em vez de reimplementar execução.
- Evitar introduzir dependências pesadas apenas para medição; `psutil` pode ser adicionada como dev-dependency se não presente, porém prefira stdlib (`tracemalloc`) quando possível.
- Performance impact: medição deve ser configurável (enable/disable) e ter overhead mensurável. Default: enabled in CI smoke runs, disabled in production heavy runs.

## References

- Source Epic: docs/planning-artifacts/epics.md#Epic-6—Modelagem-de-Portf%C3%B3lio
- PRD / Non-functional requirements: docs/planning-artifacts/epics.md (NFR-P2, NFR-P3 relevant guidance)

## Dev Agent Record

### Agent Model Used

GPT-agent (internal) – follow repo conventions

### Completion Notes List

- Criado checklist de medições e schema JSON de saída

### File List

- `src/modeling/telemetry.py` (recomendada)
- `src/main.py` (atualizar flags/CLI)
- `tests/modeling/test_metrics.py`

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/153

# Sprint Report - Story 1.5: Validação de Estrutura CSV e Flag de Linhas Inválidas

Status: completed

Resumo do que foi implementado:

- Implementado `src/validation.py` com:
  - `validate_dataframe(df, schema)` — validação leve de colunas canônicas, coerção de tipos, verificação `high >= low` e detecção de volumes negativos.
  - `ValidationSummary` e `ValidationError`.
  - `check_threshold(summary, threshold, abort_on_exceed)` para aplicar a política de tolerância.
  - `persist_invalid_rows` e `log_invalid_rows` — helpers para persistir CSVs de inválidos e registrar entradas em `metadata/ingest_logs.json`.
  - `validate_and_handle(...)` — função de integração que executa validação, persiste inválidos, registra logs e aplica `check_threshold`.

- Integração mínima com a CLI:
  - Flag `--validation-tolerance` adicionada ao entrypoint `src/main.py` (Typer) e passada para o validador.
  - Comportamento: o ingest para um ticker é abortado se invalid_percent >= threshold (abort_on_exceed=True).

- Documentação atualizada:
  - `docs/schema.json` contém o esquema canônico (colunas e tipos esperados).
  - `src/validation_schema.py` adiciona loader opcional para `pandera`.
  - `docs/playbooks/quickstart-ticker.md` atualizado com instruções de uso e configuração da validação.
  - `docs/implementation-artifacts/1-5-validar-estrutura-csv-e-filtrar-flag-rows-invalidas.md` atualizado com progresso e arquivos modificados.

  Testes e validação

  - A suíte de testes unitários foi executada localmente após implementação: **75 passed**, 16 warnings (`poetry run pytest`).

  Arquivos entregues / alterados

  - `src/validation.py` (novo): validação, persistência e logging.
  - `src/main.py` (modificado): flag `--validation-tolerance` integrada.
  - `tests/test_validation_persistence.py`, `tests/test_validation_normalize.py` (novos): cobertura para persistência e normalização.
  - `docs/implementation-artifacts/1-5-validar-estrutura-csv-e-filtrar-flag-rows-invalidas.md` (atualizado): story marcada como `done` e resumo de implementação.
  - `docs/implementation-artifacts/1-5-validation-updates.md` (adicional): resumo técnico das mudanças.


Arquivos modificados/criados:

- src/validation.py (novo)
- src/validation_schema.py (novo)
- src/main.py (adicionado flag e chamada ao validador)
- docs/playbooks/quickstart-ticker.md (atualizado)
- docs/implementation-artifacts/1-5-validar-estrutura-csv-e-filtrar-flag-rows-invalidas.md (atualizado)
- docs/sprint-reports/1-5-implementacao.md (novo)

Racional das decisões de implementação

- Validação leve em `src/validation.py` (pandas-only): optou-se por uma implementação conservadora usando pandas para reduzir complexidade e dependências adicionais, garantindo testabilidade rápida em ambientes onde instalar toda a stack pode ser oneroso; mantido um loader opcional `src/validation_schema.py` para usar `pandera` quando disponível para validação mais rígida.
- Reaproveitamento de `save_raw_csv` (persistência em `raw/<provider>/...`): reutilizar o mecanismo existente garante escrita atômica, geração consistente de checksum e `job_id`, evitando a necessidade de inicializar esquemas DB adicionais apenas para metadados.
- Registro estruturado em `metadata/ingest_logs.json` (`log_invalid_rows`): formato JSON-array é compatível com o pipeline atual, facilita auditoria manual e ingestão por ferramentas de batch/CI, e é simples de validar em ambientes restritos.
- Função de integração `validate_and_handle(...)`: centraliza fluxo (validar → persistir inválidos → logar → aplicar threshold) para simplificar orquestração (CLI/ingest) e testes automatizados, reduzindo duplicação de lógica.
- Threshold configurável via VAR de ambiente e flag CLI (`VALIDATION_INVALID_PERCENT_THRESHOLD` / `--validation-tolerance`): permite política operacional por default e overrides ad‑hoc para debugging/CI sem alterar código.
- Códigos de falha (ex.: `MISSING_COL`, `BAD_DATE`, `NON_NUMERIC_*`, `NEGATIVE_VOLUME`, `HIGH_LT_LOW`): adotados para fornecer taxonomia simples, suficiente para métricas agregadas e triagem inicial de causas.
- Importações locais em pontos críticos (ex.: `main.py`, helpers de persistência): reduzem overhead no startup do CLI (`--help`) e evitam exigir dependências pesadas em ambientes que só consultam a documentação.
- Testes e smoke runner: incluídos para permitir verificação rápida sem instalar toda a stack (smoke runner) e manter conjunto de testes `pytest` para CI.

## Atualizações da implementação — Story 1-5

Resumo das alterações implementadas para a história "Validar estrutura CSV e filtrar flag rows inválidas":

- `src/validation.py`
  - `validate_and_handle`: integração de validação + persistência + logging + threshold.
  - Normalização: conversão de `date` para timezone-aware, coerção de `open/high/low/close` para numérico e `volume` para `Int64`.
  - Extração de falhas: heurística para mapear checagens DataFrame (ex.: `high > low`) às linhas específicas quando possível.
  - Persistência: `persist_invalid_rows` escreve CSVs em `raw/<provider>/invalid-<ticker>-<ts>.csv`.
  - Logging: `log_invalid_rows` append em `metadata/ingest_logs.json` com detalhes e contagem.

- Tests adicionados:
  - `tests/test_validation_persistence.py` — valida persistência e log em `tmp_path`.
  - `tests/test_validation_normalize.py` — valida coerção de tipos e normalização de datas.

Como usar:

1. Ajuste a variável de ambiente `VALIDATION_INVALID_PERCENT_THRESHOLD` (ex: `0.10` ou `10`) para mudar o threshold padrão.
2. A CLI já expõe `--validation-tolerance` e será repassada ao pipeline.

Observações e próximos passos:


Próximos passos e observações

- Opcional: adicionar fixtures inválidos para exemplos em `tests/fixtures/`.
- Revisar e ajustar códigos de falha (`reason_code`) conforme necessidades de monitoramento/telemetria.

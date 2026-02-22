## Atualizações da implementação — Story 1-5

Resumo das alterações implementadas para a história "Validar estrutura CSV e filtrar flag rows inválidas":

- `src/validation.py`
  - `validate_and_handle`: integração de validação + persistência + logging + threshold.
  - Normalização: conversão de `date` para timezone-aware, coerção de `open/high/low/close` para numérico e `volume` para `Int64`.
  - Extração de falhas: heurística para mapear checagens DataFrame (ex.: `high > low`) às linhas específicas quando possível.
  - Persistência: `persist_invalid_rows` escreve CSVs em `raw/<provider>/invalid-<ticker>-<ts>.csv`.
  - Logging: `log_invalid_rows` append em `metadata/ingest_logs.json` com detalhes e contagem.

- Testes adicionados:
  - `tests/test_validation_persistence.py` — valida persistência e log em `tmp_path`.
  - `tests/test_validation_normalize.py` — valida coerção de tipos e normalização de datas.

Como usar:

1. Ajuste a variável de ambiente `VALIDATION_INVALID_PERCENT_THRESHOLD` (ex: `0.10` ou `10`) para mudar o threshold padrão.
2. A CLI já expõe `--validation-tolerance` e será repassada ao pipeline.

Notas e próximos passos:

- Melhorar heurísticas de categorização de erros para casos complexos.
- Ampliar testes de integração end-to-end com arquivos raw reais.

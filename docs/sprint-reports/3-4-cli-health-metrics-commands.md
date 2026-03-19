# Sprint Report: Story 3.4 - CLI Health / Metrics / Test-Conn

## O que foi implementado

- Comandos CLI adicionais em `src/main.py`:
  - `main test-conn` (verifica conectividade de providers)
  - `main metrics` (métricas básicas de ingestão / saúde)
  - `main health` (saúde local de DB e diretórios + métricas)

- Novos helpers de health/metrics em `src/utils/`:
  - `src/utils/health.py` (leitura de logs ingest, computação de métricas, verificação de paths)
  - `src/utils/metrics_prometheus.py` (módulo Prometheus com fallback / no-op)

- Contrato de conectividade unificado:
  - `Adapter.check_connection(timeout)` adicionado em `src/adapters/base.py`
  - Implementação de `check_connection` no adaptador `yfinance`
  - `src/connectivity.py` agora retorna `last_success_at` e grava falhas em `metadata/ingest_logs.jsonl`

- Testes adicionados:
  - `tests/test_cli_test_conn.py` valida a saída e os códigos de saída do `test-conn`.
  - `tests/test_cli_health_metrics.py` valida a saída do `health` e `metrics` e a estrutura JSON.

- Documentação atualizada:
  - `docs/playbooks/quickstart-ticker.md` possui novos exemplos de uso para `test-conn`, `metrics`, `health`.

## Como testar

```bash
poetry run pytest -q tests/test_cli_health_metrics.py
```

Para uso manual:

```bash
poetry run main test-conn --provider dummy --format json
poetry run main metrics --format json
poetry run main health --format json
```

## Próximos passos sugeridos

- [ ] Rever e completar a documentação de `src/utils/logging.py` (se precisar de wrapper adicional)
- [ ] Atualizar as métricas armazenadas (e.g. `rows_fetched`) no pipeline para que `metrics` seja mais rico
- [ ] Cobrir ambientes de CI/produção que executam `main health` como check pré-implantação

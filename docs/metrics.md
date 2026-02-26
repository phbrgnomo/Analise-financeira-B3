Telemetria e métricas

Configuração disponível
- `PROMETHEUS_METRICS`: quando definida (qualquer valor), o CLI tentará
  iniciar um servidor HTTP para expor métricas Prometheus.
- `PROMETHEUS_METRICS_PORT`: porta TCP (padrão `8000`) para o servidor de métricas.

Como habilitar (exemplo):

```bash
export PROMETHEUS_METRICS=1
export PROMETHEUS_METRICS_PORT=9000
poetry run python -m src.main compute-returns --ticker PETR4.SA
```

Métricas expostas (resumo esperado)
- `returns_job_duration_ms{ticker="PETR4.SA"}` — duração em ms do job
- `returns_rows_written{ticker="PETR4.SA"}` — número de linhas gravadas
- `returns_last_job_id` — id do último snapshot/execução

Observações de implementação
- O código já contém um ponto de inicialização que verifica `PROMETHEUS_METRICS`
  e chama `metrics.start_metrics_server(port)` (ver `src/main.py`).
- As métricas são instrumentadas na camada de ingest/retorno e também em
  `src/retorno.py`/`src/db.py` quando snapshots são gravados. Este documento
  descreve apenas como habilitar; adicionar uma stack de coleta/alertas (Prometheus+
  Grafana) é um passo operacional externo a este repositório.

Testes para telemetria
- Para testar localmente, habilite a variável de ambiente e verifique o endpoint:

```bash
export PROMETHEUS_METRICS=1
poetry run python -m src.main compute-returns --ticker PETR4.SA --dry-run &
curl http://localhost:8000/metrics
```

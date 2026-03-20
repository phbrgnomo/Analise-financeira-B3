# Telemetria e métricas

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

Métricas expostas (resumo observado)
- `compute_returns_total` — contador de execuções de `compute_returns`
- `compute_returns_duration_ms` — histograma/observação da duração em ms de `compute_returns`

Observação de depreciação: o módulo legado `src.metrics` está depreciado e
será removido na versão `v2.0.0` (ou posterior). Use `src.utils.metrics_prometheus`
como substituto.

Migração rápida:

- antes:
  ```python
  from src.metrics import start_metrics_server, observe_counter
  ```
- depois:
  ```python
  from src.utils.metrics_prometheus import start_metrics_server, observe_counter
  ```

- no `src.main.py` e outros módulos que importavam `src.metrics`, atualize para
  importar `src.utils.metrics_prometheus`.

- diferenças de API:
  - `src.utils.metrics_prometheus` foi projetado como wrapper leve; não adiciona
    labels automaticamente. Adicione `labels` manualmente onde necessário.
  - ver `src.utils.metrics_prometheus` para funções expostas e convenção de nomes.

Nota: `src.metrics` permanecerá funcional no `v1.x`, mas usuários devem migrar
antes de `v2.0.0`.

Observação: o código grava `rows_written` e `job_id` como metadados de snapshot
via `repo.record_snapshot_metadata(...)` (armazenado em `snapshots/` ou na tabela
`snapshots`), mas esses valores não são expostos automaticamente como métricas
Prometheus pelo wrapper atual. O wrapper `src.utils.metrics_prometheus` é
intencionalmente leve e não adiciona labels automaticamente; se desejar métricas
rotuladas (`ticker` etc.) ou métricas adicionais (`returns_rows_written`,
`returns_last_job_id`) é possível estender `src.utils.metrics_prometheus` para
suportar labels
e incrementar/observar essas métricas no ponto de persistência (`_persist_returns`).

Observações de implementação
- O código já contém um ponto de inicialização que verifica `PROMETHEUS_METRICS`
  e chama `src.utils.metrics_prometheus.start_metrics_server(port)`
  (ou: `from src.utils import metrics_prometheus as metrics` e
  `metrics.start_metrics_server(port)`; ver `src/main.py`).
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

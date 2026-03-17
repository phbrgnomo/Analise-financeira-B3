# Health & Metrics Schema (CLI / API)

Este documento define o contrato de estrutura de dados e limites (thresholds) utilizados pelos comandos de health e metrics do CLI (`main --metrics`, `main --test-conn`, etc.).

## 1. Terminologia

- `ingest_lag`: tempo em segundos desde a última ingestão bem-sucedida para um ticker.
- `job_id`: identificador único (UUID) para uma execução de ingest.

## 2. Thresholds padrão

- **ingest_lag**: 86400 (24 horas)
- **validation_invalid_percent_threshold**: 0.10 (10%)

Esses valores podem ser sobrescritos via variáveis de ambiente (`INGEST_LAG_THRESHOLD`, `VALIDATION_INVALID_PERCENT_THRESHOLD`) quando suportado pelo CLI.

## 3. Schema JSON (Health / Metrics)

### Exemplo de saída (`main --metrics`)

```json
{
  "status": "healthy|degraded|unhealthy",
  "timestamp": "2026-03-16T12:34:56Z",
  "metrics": {
    "ingest_lag_seconds": 43200,
    "errors_last_24h": 0,
    "jobs_last_24h": 5,
    "avg_latency_seconds": 3.2
  },
  "thresholds": {
    "ingest_lag_seconds": 86400
  }
}
```

### Campos obrigatórios

- `status` (string): `healthy`, `degraded` ou `unhealthy`
- `timestamp` (string, RFC3339 UTC)
- `metrics` (object) com: `ingest_lag_seconds` (int), `errors_last_24h` (int), `jobs_last_24h` (int), `avg_latency_seconds` (number)
- `thresholds` (object) com: `ingest_lag_seconds` (int)

## 4. Uso em CI / monitoramento

- Um check de saúde pode falhar se `status` for `degraded` ou `unhealthy`.
- Ferramentas de monitoramento podem consultar `main --metrics --format json` e comparar `metrics.ingest_lag_seconds` com `thresholds.ingest_lag_seconds`.

## 5. Test-conn

O comando `main --test-conn --provider <name>` deve retornar JSON no formato:

```json
{
  "status": "success|failure",
  "provider": "yfinance",
  "latency_ms": 123,
  "error": null
}
```

E usar exit codes padrão: `0` para success, `2` para failure.

# Health & Metrics Schema (CLI / API)

Este documento define o contrato de estrutura de dados e limites (thresholds) utilizados pelos comandos de health e metrics do CLI (`main --metrics`, `main --test-conn`, etc.).

## 1. Terminologia

- `ingest_lag`: tempo em segundos desde a última ingestão bem-sucedida para um ticker.
- `job_id`: identificador único (UUID) para uma execução de ingest.

## 2. Thresholds padrão

- **ingest_lag**: 86400 (24 horas)
- **validation_invalid_percent_threshold**: 0.10 (10%)

Esses valores podem ser sobrescritos via variáveis de ambiente (o CLI lê o valor do ambiente no momento da execução):

- `INGEST_LAG_THRESHOLD` (usado pelo comando `main --metrics`; também pode ser fornecido via `--threshold`).
- `VALIDATION_INVALID_PERCENT_THRESHOLD` (usado pelo pipeline de ingestão/validação; configure antes de executar `main run`).

Exemplo:

```bash
INGEST_LAG_THRESHOLD=3600 poetry run main --metrics --format json
VALIDATION_INVALID_PERCENT_THRESHOLD=0.05 poetry run main run --ticker PETR4
```

## 3. Schema JSON (Health / Metrics)

### Exemplo de saída (`main --metrics`)

Exemplo de execução (modo padrão):

```bash
poetry run main --metrics --format json
```

Exemplo com arquivo de configuração explícito (opcional):

```bash
poetry run main --metrics --format json --config /path/to/config.toml
```

Saída esperada (JSON):

```json
{
  "status": "healthy",
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

- `status` (string): `healthy`, `degraded`, `unhealthy` ou `unknown`
- `timestamp` (string, RFC3339 UTC)
- `metrics` (object) com: `ingest_lag_seconds` (int|null), `errors_last_24h` (int), `jobs_last_24h` (int), `avg_latency_seconds` (number)
- `thresholds` (object) com: `ingest_lag_seconds` (int)

## 4. Uso em CI / monitoramento

### Comportamento esperado

- Um check de saúde deve ser considerado **falho** se:
  - O comando retorna **exit code != 0** (erro de execução, arquivo inacessível, etc.).
  - A saída não for JSON válido.
  - O JSON não contiver os campos obrigatórios (`status`, `metrics.ingest_lag_seconds`, `thresholds.ingest_lag_seconds`).

- O campo `status` é calculado a partir de `metrics.ingest_lag_seconds` e `errors_last_24h` conforme a lógica implementada em `src/utils/health.py`:
  - `healthy`: `ingest_lag_seconds <= threshold_seconds` e `errors_last_24h == 0`
  - `degraded`: `ingest_lag_seconds > threshold_seconds` **ou** `errors_last_24h > 0`
  - `unhealthy`: `ingest_lag_seconds > threshold_seconds * 2`
  - `unknown`: valores ausentes ou inválidos em `metrics.ingest_lag_seconds` ou `errors_last_24h`, ou valores não parseáveis (ex.: `null` ou indefinido)

  > Para o valor padrão de `threshold_seconds = 86400` (24h):
  > - `degraded` quando `ingest_lag_seconds > 86400` (mais de 24h sem ingestão)
  > - `unhealthy` quando `ingest_lag_seconds > 172800` (mais de 48h sem ingestão)
  > - `unknown` quando `metrics` está ausente, contém `null` ou valores inválidos.
### Recomendações para ferramentas de monitoramento

- Execute `main --metrics --format json` em um agendador/cron e trate como **falha de conexão** quando:
  - o comando não terminar dentro de um timeout razoável (recomendado: **30s**).
  - o comando retorna código de saída diferente de `0`.
  - a saída não é JSON válido ou não contém os campos esperados.

- Em caso de falha transitória (ex: arquivo de log momentaneamente inacessível, bloqueio de I/O):
  1. Repetir com backoff exponencial (ex.: 1s → 2s → 4s) até 3 tentativas.
  2. Se todas as tentativas falharem, elevar a severidade do alerta (por exemplo, **P1/P0**) pois o sistema pode estar indisponível.

- Ao parsear o JSON:
  - Valide que `metrics.ingest_lag_seconds` é um número (ou `null`, que indica ausência de ingestões registradas).
  - Valide que `status` está entre `healthy|degraded|unhealthy|unknown`.
  - Compare `metrics.ingest_lag_seconds` (quando não `null`) com `thresholds.ingest_lag_seconds` para derivar alertas adicionais, se necessário.

### Edge cases e limitações

- Se o arquivo de logs (`metadata/ingest_logs.jsonl`) não existe ou está vazio, o comando retorna `status: "unknown"` e `metrics.ingest_lag_seconds: null`.
- O CLI não implementa retries/timeout por conta própria; essa responsabilidade é do consumidor (CI/monitoramento).
- O cálculo de `ingest_lag_seconds` depende da última execução registrada com `finished_at` válido. Registros malformados são ignorados.
- Não há limite de taxa interno (`rate limiting`); no entanto, evite rodar o comando com alta frequência (ex.: <1m) em ambientes com armazenamento lento, pois a leitura do log pode ser custosa.

## 5. Test-conn

O comando `main --test-conn --provider <name>` valida a conectividade do adapter/provider e retorna JSON com um resumo simples.

### Schema de saída (`--format json`)

```json
{
  "status": "success|failure",
  "provider": "yfinance",
  "latency_ms": 123.45,
  "error": null
}
```

- `status` (string): `success` quando o teste passou; `failure` quando falhou.
- `provider` (string): echo do valor passado em `--provider` (p.ex. `yfinance`).
- `latency_ms` (number): tempo total gasto na chamada em milissegundos. Atualmente o CLI sempre mede e retorna um valor numérico mesmo em falhas (caso raro em que a medição não seja possível, pode ser `null`).
- `error` (string|null): mensagem de erro detalhada em caso de falha. No momento, sempre é uma string quando `status` é `failure`.

### Exit codes do comando

O comando utiliza exit codes simples (não há distinção fina entre tipos de falha):

- `0`: sucesso (`status == "success"`).
- `1`: erro geral / exceção inesperada (não é usado pelo `--test-conn` atual, mas pode aparecer em outros comandos do CLI).
- `2`: qualquer tipo de falha de conectividade ou validação do provider (`status == "failure"`).

> Nota: o CLI não diferencia códigos para falhas de autenticação, timeouts ou provider inválido — tudo é exibido como `failure` e sai com código `2`. Caso você precise de distinções mais finas, valide o campo `error` na saída JSON.

### Exemplos de saída de falha (JSON)

#### Provider inválido

```json
{
  "status": "failure",
  "provider": "does-not-exist",
  "latency_ms": 3.21,
  "error": "unknown adapter provider: 'does-not-exist'"
}
```

#### Erro de autenticação / rede (exemplo hipotético)

```json
{
  "status": "failure",
  "provider": "yfinance",
  "latency_ms": 1500.0,
  "error": "request timed out after 30s"
}
```

### Comportamento esperado em casos específicos

- **Provider inválido**: o comando retorna `status: "failure"`, `provider` ecoa o nome informado, e `error` contém uma mensagem clara como `unknown adapter provider: '<nome>'`. Sai com código `2`.

- **Timeout de rede / indisponibilidade temporária**: se o adapter implementar uma chamada de rede em `test_connection` e ela falhar (por exemplo, timeout, conexão recusada, 5xx), o comando retorna `status: "failure"`, `error` terá a mensagem de exceção na camada de adapter, e o exit code é `2`. O CLI não aplica retries adicionais para `--test-conn` (além do que o adapter já fizer internamente).

- **Falhas de autenticação**: apesar de o CLI não distinguir explicitamente esse caso, a mensagem em `error` deverá indicar o problema (por exemplo, `authentication failed`).

- **Formato do campo `error`**: atualmente é sempre uma mensagem de texto (`string`) ou `null` quando não há erro. Não há parsing de JSON/objetos estruturados.

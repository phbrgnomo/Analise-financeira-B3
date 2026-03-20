# Quickstart: ingest → persist → snapshot → notebook

Este playbook descreve os passos mínimos para reproduzir o fluxo ingest→persist→snapshot→notebook usando um ticker de amostra.

Pré-requisitos
- Python 3.12+ (virtual env/poetry recomendado)
- Dependências instaladas: `poetry install` (ou conforme `pyproject.toml`)
- Banco local SQLite em `dados/data.db` (o projeto cria quando necessário)

Exemplo rápido

1. Executar ingest e persist (forçando refresh):

```bash
poetry run main --ticker PETR4 --force-refresh
```

2. Opcionalmente, executar o notebook de análise (se `papermill` estiver instalado):

```bash
poetry run main --ticker PETR4 --run-notebook
```

3. Exemplo em modo CI / offline simulando caixa preta:

```bash
poetry run main --ticker PETR4 --format json --no-network
```

4. Exemplo usando um conjunto personalizado de tickers ou limitando o período de ingestão:

```bash
poetry run main --sample-tickers PETR4,ITUB3 --max-days 30 --no-network
```

> Para uso em CI ou em scripts, você pode gerar saída JSON e rodar em modo offline:
>
> ```bash
> poetry run main --ticker PETR4 --format json --no-network
> ```
>
> O JSON segue o contrato descrito em `CLI_CONTRACT.md`.
>
> **Nota:** mesmo em modo `--no-network`, o pipeline ainda grava snapshots locais e irá reutilizar (cache hit) os arquivos existentes sempre que o conteúdo não mudar. Mesmo nesses casos, o JSON continua a incluir `snapshot_path` e `snapshot_checksum` para permitir validação consistente em CI.
>
> **Observação sobre `--run-notebook`:**
> O notebook é executado apenas se você passar `--run-notebook`, e pode precisar de rede dependendo do conteúdo das células (mesmo em `--no-network`).

2. Arquivos/paths esperados (exemplos):
- Snapshot CSV: `snapshots/<TICKER>-YYYYMMDD.csv` (ex.: `snapshots/PETR4-20260215.csv`)
- Banco SQLite: `dados/data.db`
- Relatórios derivados: `reports/PETR4_report.csv` (quando aplicável)
- Raw provider CSVs: `raw/<provider>/<TICKER>-YYYYMMDDTHHMMSSZ.csv`
- Checksum ao lado do raw CSV: `snapshots/<TICKER>-YYYYMMDD.csv.checksum` (ou `raw/<provider>/<TICKER>-YYYYMMDDTHHMMSSZ.csv.checksum` para arquivos raw)
- Metadados de ingestão (JSONL, append-only): `metadata/ingest_logs.jsonl` (uma linha JSON por ingest com `job_id, source, fetched_at, raw_checksum, rows, filepath, status, created_at`)

Verificações mínimas

- Verificar existência do snapshot (o nome contém data no formato `YYYYMMDD`):

```bash
ls -l snapshots/PETR4-*.csv
```

- Calcular checksum SHA256 do snapshot (ou validar contra o arquivo `.checksum` gerado automaticamente):

```bash
sha256sum snapshots/PETR4-20260215.csv
# Exemplo de saída (valor fictício para demonstração):
# 5f2a3d09b88b34f284d0c2da5e8b6aa9c0e4e5309af25b0f90e9f8157f2089fa  snapshots/PETR4-20260215.csv

# Verificar que o checksum bate com o arquivo sidecar:
cat snapshots/PETR4-20260215.csv.checksum
```

Verificar raw provider e metadados

```bash
# a pasta raw usa o ticker no formato do provedor (yfinance inclui ".SA")
ls -l raw/yfinance/PETR4.SA-*.csv
# o comando CLI/ingest abaixo aceita o ticker base sem sufixo
# (PETR4) — a tradução é feita internamente pela fábrica de adapters
# ver última entrada JSONL
tail -n 1 metadata/ingest_logs.jsonl | jq '.'
```

Observação: a implementação atual grava metadados em `metadata/ingest_logs.jsonl` (JSON Lines append-only). Para exigir permissões owner-only nos artefatos, chame a função com `set_permissions=True` ou aplique `chmod 600` manualmente.

Banco de dados local
- Inicialize o banco SQLite (se ainda não existir):

```bash
poetry run python scripts/init_ingest_db.py --db dados/data.db
```

O pipeline também tenta persistir automaticamente as linhas canônicas no banco via `db.write_prices()` quando o mapeamento canônico e a validação forem bem-sucedidos.

- Abrir notebook de análise (ex.: `notebooks/quickstart.ipynb`) e executar células necessárias para gerar os plots esperados.

Comandos de troubleshooting

- Forçar ingest completo ignorando cache do pipeline:

```bash
poetry run main --ticker PETR4 --force-refresh
```

### Saúde, métricas e conectividade

- Verificar conectividade com o provider (saída JSON):

```bash
poetry run main test-conn --provider dummy --format json
```

- Verificar métricas de ingestão (saída JSON):

```bash
poetry run main metrics --format json
```

- Verificar saúde básica do sistema local (BD + diretórios):

```bash
poetry run main health --format json
```

## 🧾 Saída JSON esperada (schema)

### `test-conn` (conectividade com provider)

Exemplo de schema retornado por `poetry run main test-conn --format json`:

```json
{
  "status": "success" | "failure",
  "provider": "yfinance",                        // provider solicitado
  "latency_ms": 12.34,                            // tempo de resposta em ms
  "last_success_at": "2026-03-18T12:34:56Z" | null,
  "error": null | "<mensagem de erro>"
}
```

- **Exit code:** `0` em sucesso (`status == "success"`), `2` em erro (`status == "failure"`).
- **Edge cases:**
  - Provider indisponível / sem rede: `status: "failure"`, `error` com mensagem de conexão (e.g. "gaierror" ou "timeout").
  - Provider desconhecido ou sem suporte a `test-conn`: `status: "failure"` e `error: "provider does not support test-conn"`.
  - Em caso de falha, o CLI também grava um registro no `metadata/ingest_logs.jsonl` para observabilidade.

### `metrics` (health de ingestão)

Exemplo de schema retornado por `poetry run main metrics --format json`:

```json
{
  "status": "healthy" | "degraded" | "unhealthy" | "unknown",
  "timestamp": "2026-03-18T12:34:56Z",
  "metrics": {
    "ingest_lag_seconds": 123.45 | null,
    "errors_last_24h": 0,
    "jobs_last_24h": 0,
    "avg_latency_seconds": 0.123 | null
  },
  "thresholds": {
    "ingest_lag_seconds": 86400
  }
}
```

- **Exit code:** `0` (não há falhas no comando em si; qualquer problema geralmente é refletido no campo `status`).
- **Edge cases:**
  - Arquivo de log `metadata/ingest_logs.jsonl` ausente ou vazio => `status: "unknown"`, `ingest_lag_seconds: null`, `avg_latency_seconds: null`, `errors_last_24h: 0`, `jobs_last_24h: 0`.

### `health` (saúde local + métricas)

Exemplo de schema retornado por `poetry run main health --format json`:

```json
{
  "status": "ok" | "warn" | "error",
  "paths": {
    "status": "ok" | "warn" | "error",
    "reasons": ["<mensagem de problema>"]
  },
  "metrics": {
    "status": "healthy" | "degraded" | "unhealthy" | "unknown",
    "timestamp": "2026-03-18T12:34:56Z",
    "metrics": {
      "ingest_lag_seconds": 123.45 | null,
      "errors_last_24h": 0,
      "jobs_last_24h": 0,
      "avg_latency_seconds": 0.123 | null
    },
    "thresholds": {
      "ingest_lag_seconds": 86400
    }
  }
}
```

- **Exit code:** `0` (o comando não falha, apenas relata o estado dos caminhos e métricas).
- **Edge cases:**
  - Banco de dados ausente: `paths.status` geralmente será `warn` e `paths.reasons` inclui `"db missing: ..."`.
  - Banco de dados existe mas não é legível (permissões): `paths.status` será `error` e `paths.reasons` incluirá algo como `"db unreadable: [Errno ...]"`.
  - Diretórios `raw/` ou `snapshots/` ausentes ou não são diretórios: `paths.status` será `warn` e `paths.reasons` incluirá mensagens como `"raw not a directory: ..."`.

Notas de exemplo e outputs

- Ao executar o quickstart, um CSV com colunas OHLCV e uma coluna `Return` deve ser persistido no snapshot.
- O checksum é usado para validação automatizada no CI (verificar `snapshots_test/` para exemplos e fixtures).

Checklist de verificação (mínimo)

- [ ] Executou o comando de ingest com sucesso
- [ ] Snapshot gerado em `snapshots/` com o nome esperado
- [ ] Checksum SHA256 calculado e conferido
- [ ] Notebook relacionado abre e gera os plots esperados

Referências
- Arquitetura: docs/planning-artifacts/architecture.md
- PRD: docs/planning-artifacts/prd.md

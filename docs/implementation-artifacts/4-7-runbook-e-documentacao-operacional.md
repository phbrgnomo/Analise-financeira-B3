---
title: "4.7 Runbook e Documentação Operacional"
epic: 4
story: 4.7
status: ready-for-dev
owner: Operator / Tech Writer
generated_by: create-story workflow
---

# Story 4.7: Runbook e documentação operacional

Status: ready-for-dev

As an Operator / Tech Writer,
I want a concise operational runbook describing common diagnoses and commands,
so that on-call engineers can follow step-by-step recovery and troubleshooting instructions.

## Resumo

Este documento entrega um runbook operacional conciso e acionável para as tarefas mais comuns de operação e recuperação do projeto Analise-financeira-B3. Inclui comandos exemplares, saídas esperadas, verificações de integridade, backup/restore, como interpretar `main metrics` e `ingest_logs`, e caminhos de escalonamento.

## Acceptance Criteria (extraído do Epic)

- Arquivo: `docs/operations/runbook.md` (nesta story o conteúdo fica em `docs/implementation-artifacts/4-7-runbook-e-documentacao-operacional.md` — mover para `docs/operations/` quando aprovado)
- Contém instruções para: checar `ingest_logs`, executar `main backup --restore`, interpretar `main metrics`, verificar checksum de snapshots, e caminhos de escalonamento.
- Inclui comandos de exemplo e saídas esperadas para modos comuns de falha.

## Quickstart operacional (comandos essenciais)

- Listar métricas (human-readable):

  ```bash
  poetry run main metrics
  ```

  Saída esperada (exemplo):

  ```text
  Ticker: PETR4.SA | Last ingest: 2026-02-15T12:34:56Z | Ingest lag: 3600s | Job latency avg: 1234ms | Rows: 42 | Errors: 0
  ```

- Métricas em JSON (para CI/automação):

  ```bash
  poetry run main metrics --format json
  ```

  Schema mínimo esperado:

  ```json
  {
    "ticker": "PETR4.SA",
    "last_ingest": "2026-02-15T12:34:56Z",
    "ingest_lag_seconds": 3600,
    "job_latency_ms": 1234,
    "rows_fetched": 42,
    "error_count": 0
  }
  ```

- Verificar conectividade com provider (test-conn):

  ```bash
  poetry run main test-conn --provider yfinance
  ```

  Saída: status de sucesso com latência; exit codes semânticos (0=OK,1=Warning,2=Critical)

- Consultar logs de ingestão (filtrar por ticker / data):

  ```bash
  poetry run main logs --ticker PETR4.SA --since 2026-02-01 --format json
  ```

  Saída JSON: entradas com os campos `ticker`, `job_id`, `started_at`, `finished_at`, `rows_fetched`, `status`, `error_message`, `duration_ms`, `provider`, `attempt`, `retry_after` (nullable)

## Backup & Restore (comandos e verificação)

- Criar backup atômico (escrever em temp + rename) e gerar checksum:

  ```bash
  poetry run main backup --create --out backups/backup-$(date -u +%Y%m%dT%H%M%SZ).db --verify
  ```

  - Arquivo resultante: `backups/backup-YYYYMMDDTHHMMSSZ.db`
  - Arquivo companion: `backups/backup-YYYYMMDDTHHMMSSZ.db.checksum` (SHA256)
  - Permissões recomendadas: `chmod 600 backups/*.db`

- Restaurar backup e verificar integridade:

  ```bash
  poetry run main backup --restore --from backups/backup-20260215T120000Z.db
  ```

  Procedimento de verificação: restauração em DB temporário + contagens básicas (rows por tabela) + comparação de checksum

## Snapshot checksum validation (CI)

- Regra de CI (exemplo): gerar snapshot CSV e `.checksum` file; comparar SHA256; falhar pipeline se mismatch.

  Comando (local/CI):

  ```bash
  # gerar snapshot (modo --no-network para CI fixtures)
  poetry run main --no-network --ticker PETR4.SA --format json
  # calcular checksum
  sha256sum snapshots/PETR4-20260215.csv > snapshots/PETR4-20260215.csv.checksum
  ```

## Troubleshooting — passos rápidos (fork in order)

1. Problema: `main metrics` indica ingest-lag alto (> METRICS_INGEST_LAG_THRESHOLD):
   - Verifique `poetry run main logs --since <date>` para últimos erros
   - Cheque jobs em andamento e locks (um job por ticker por vez)
   - Se há falhas por provider, rodar `poetry run main test-conn --provider <name>`
   - Se DB inacessível, rodar `poetry run main backup --restore --from <backup>` em ambiente de teste

2. Problema: snapshot checksum mismatch:
   - Re-run snapshot generation with `--no-network` in CI fixtures
   - Compare CSV header e última linhas; verificar `raw/` e `snapshots/` files
   - Publish artifact CSV + .checksum to CI for investigation

3. Problema: logs mostram `rate-limit` do provider:
   - Ver retry_after, aguardar ou ajustar `ADAPTER_MAX_RETRIES` e backoff
   - Registrar evento para suporte e considerar re-schedule

## Operational defaults (env vars) — referencias rápidas

- `DATA_DIR=./dados`
- `SNAPSHOT_DIR=./snapshots`
- `BACKUP_DIR=./backups`
- `LOG_LEVEL=INFO`
- `ADAPTER_MAX_RETRIES=3`
- `VALIDATION_INVALID_PERCENT_THRESHOLD=10`  # percent
- `INGEST_LOCK_TIMEOUT_SECONDS=120`
- `METRICS_INGEST_LAG_THRESHOLD=86400`  # seconds (24h)

## Escalonamento e contatos

- Primeiro nível: Dev/On-call (owner do último commit) — reproduzir em ambiente local/CI e recolher artifacts (CSV + .checksum + logs)
- Segundo nível: Arquiteto (para decisões de DB/migration/arquitetura)
- Tech Writer / PM: avaliar documentação e comunicar alterações no README/playbooks

## Implementação recomendada (guia rápido para devs)

- CLI: adicionar subcomandos `metrics`, `logs`, `backup` seguindo padrões Typer (entrypoint `main`).
- Logs: JSON estruturado com campos mínimos (ver seção acima).
- Backup: atomic write + `.checksum` + `chmod 600` + `--verify` option.
- CI: jobs que podem rodar `--no-network` usando fixtures em `tests/fixtures/`.

## Testes e validação

- Unit tests: cobrir parsing de `ingest_logs`, geração de checksum e backup/restore logic.
- Integration (CI): fixture-based snapshot generation + checksum validation; publicar artifacts.

## Referências e fontes

- Epic details: `docs/planning-artifacts/epics.md` (seção "Epic 4 — Operações & Observabilidade")
- Operational defaults: seção "Operational defaults, env vars e exemplos" em `epics.md`
- Exemplo fixtures: `tests/fixtures/`

## Notas do gerador

- Gerado automaticamente pelo workflow `create-story` com análise de `epics.md` e `sprint-status.yaml`.
- Próximo passo sugerido: mover para `docs/operations/runbook.md` e revisar com Tech Writer para formatação final e inclusão de exemplos reais de saída.

---

*Fim do runbook inicial.*

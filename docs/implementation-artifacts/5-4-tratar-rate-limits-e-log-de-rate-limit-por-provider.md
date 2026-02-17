---
created: 2026-02-17T00:00:00Z
story_key: 5-4-tratar-rate-limits-e-log-de-rate-limit-por-provider
epic: 5
story_num: 4
status: ready-for-dev
owner: Dev / Ops
---

# Story 5.4: Tratar rate-limits e log de rate-limit por provider

Status: ready-for-dev

## Story

As an Operator/Developer,
I want the adapters to detect and log rate-limit responses and expose retry windows,
so that retries are respectful and observable.

## Acceptance Criteria

1. Dado que um provedor responde com rate-limit ou 429, quando o adaptador receber essa resposta, ele registra o evento em `ingest_logs` com `retry_after` e `provider_rate_limit=true`.
2. Adaptadores implementam backoff exponencial com jitter e respeitam cabeçalhos `Retry-After` do provedor quando presentes.
3. Logs do adaptador incluem `provider`, `attempt`, `status_code`, `retry_after` (quando presente) e `job_id` para correlação.
4. Há testes de contrato/integração que simulam respostas 429/ratelimit via fixtures (`--no-network` / `--use-fixture`) e validam comportamento de retry e logging.
5. Documentação (docs/planning-artifacts/adapter-mappings.md) é atualizada com política de rate-limit e exemplos de log e formatos de eventos.

## Tasks / Subtasks

- [ ] Task 1: Detectar respostas de rate-limit (429) e extrair `Retry-After` quando disponível
  - [ ] Subtask 1.1: Implementar parsing seguro de cabeçalho `Retry-After` (int seconds ou HTTP-date)
  - [ ] Subtask 1.2: Mapear outros sinais de rate-limit (códigos 429, payloads específicos, headers proprietários)
- [ ] Task 2: Implementar política de retries
  - [ ] Subtask 2.1: Implementar retry com backoff exponencial + jitter
  - [ ] Subtask 2.2: Respeitar `Retry-After` quando presente (esperar o tempo indicado antes do próximo attempt)
  - [ ] Subtask 2.3: Limitar tentativas por configuração (`ADAPTER_MAX_RETRIES`, `ADAPTER_BACKOFF_BASE_MS`, `ADAPTER_BACKOFF_MAX_MS`)
- [ ] Task 3: Registro e telemetria
  - [ ] Subtask 3.1: Logar eventos em `ingest_logs` com campos: `job_id`, `provider`, `attempt`, `status_code`, `retry_after`, `provider_rate_limit` (boolean), `message`
  - [ ] Subtask 3.2: Emitir métrica de rate-limit por provider (`provider_rate_limit_count`, `provider_retry_after_ms`) para `main --metrics` / telemetry
- [ ] Task 4: Testes e fixtures
  - [ ] Subtask 4.1: Adicionar fixtures em `tests/fixtures/providers/` que simulam 429 com/sem `Retry-After`
  - [ ] Subtask 4.2: Escrever `tests/adapters/test_rate_limit_handling.py` cobrindo retries, respeito ao Retry-After e logs gravados
- [ ] Task 5: Documentação e exemplos
  - [ ] Subtask 5.1: Atualizar `docs/planning-artifacts/adapter-mappings.md` com seção de rate-limit e exemplos de logs
  - [ ] Subtask 5.2: Adicionar trecho de runbook em `docs/playbooks/quickstart-ticker.md` que descreve como interpretar e remediar rate-limits em ambiente local

## Dev Notes

- Local de implementação recomendado: `src/dados_b3.py` (adaptadores iniciais) e novo módulo `src/adapters/` para organizar providers (ex.: `src/adapters/yfinance.py`, `src/adapters/alphavantage.py`).
- Interface Adapter: seguir `Adapter.fetch(ticker) -> pd.DataFrame` e lançar exceções específicas `AdapterRateLimitError(retry_after=None, provider=...)` para permitir tratamento centralizado.
- Logging: utilizar logging estruturado (JSON) com campos mínimos: `ticker`, `job_id`, `provider`, `attempt`, `status_code`, `retry_after`, `provider_rate_limit`, `message`.
- Persistência de logs: gravar eventos de rate-limit em `ingest_logs` (pode ser tabela no `dados/data.db` ou arquivo `logs/ingest_logs.jsonl` conforme infra existente). Manter `job_id` para correlação com runs.
- Configuração: adicionar opções em `config/providers.example.yaml` e variáveis de ambiente: `ADAPTER_MAX_RETRIES`, `ADAPTER_INITIAL_BACKOFF_MS`, `ADAPTER_MAX_BACKOFF_MS`, `ADAPTER_JITTER=True`.

### Project Structure Notes

- Propondo organização mínima:
  - src/adapters/__init__.py
  - src/adapters/base.py  # define Adapter interface e exceções (AdapterRateLimitError)
  - src/adapters/yfinance.py
  - src/adapters/alphavantage.py
  - src/ingest/runner.py  # orquestrador que usa adapters e aplica retry 정책

### References

- Source: docs/planning-artifacts/epics.md#Epic-5 — Story 5.4 — Tratar rate-limits e log de rate-limit por provider

## Dev Agent Record

### Agent Model Used

GPT-generated content (agent integrated into BMad flow)

### Completion Notes List

- Story criado com base em `epics.md` (Epic 5 — Story 5.4) e template padrão de stories.

### File List

- docs/implementation-artifacts/5-4-tratar-rate-limits-e-log-de-rate-limit-por-provider.md

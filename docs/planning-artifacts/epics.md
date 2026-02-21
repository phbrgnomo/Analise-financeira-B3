---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - docs/planning-artifacts/prd.md
  - docs/planning-artifacts/architecture.md
  - docs/planning-artifacts/product-brief-Analise-financeira-B3-2026-02-15.md
  - docs/planning-artifacts/prd-validation-2026-02-15.md
  - docs/planning-artifacts/backlog.md
  - docs/planning-artifacts/adapter-mappings.md
  - docs/planning-artifacts/implementation-readiness-report-2026-02-16.md
  - docs/planning-artifacts/research
epicsApprovedBy: Phbr
epicsApprovedAt: 2026-02-16T17:45:00Z
---

# Analise-financeira-B3 - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Analise-financeira-B3, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: [Usuário/CLI] pode iniciar ingest de preços para um ticker específico.
FR2: [Sistema] pode recuperar dados de pelo menos dois provedores (Yahoo, AlphaVantage) via adaptadores.
FR3: [Sistema] pode recuperar dados de múltiplos provedores configuráveis via adaptadores.
FR4: [Sistema] grava a resposta bruta do provedor em arquivo CSV em `raw/<provider>/`.
FR5: [Sistema] inclui metadados ao persistir dados brutos (`source`, `fetched_at`, `rows`, `checksum`).
FR6: [Sistema] valida a estrutura do CSV recebido contra um schema mínimo (colunas esperadas).
FR7: [Sistema] rejeita/flag rows que não atendam ao schema e registra motivo em `ingest_logs`.
FR8: [Usuário/CLI] pode solicitar um relatório de validação de amostra para um arquivo CSV.
FR9: [Sistema] persiste dados validados no banco local (`dados/data.db`) nas tabelas mínimas (`prices`, `returns`, `ingest_logs`, `snapshots`, `metadata`).
FR10: [Sistema] realiza upsert por (ticker, date) para evitar duplicação.
FR11: [Desenvolvedor/API] pode ler preços por ticker e intervalo via contrato `db.read_prices(ticker, start, end)`.
FR12: [Desenvolvedor/API] pode gravar preços via contrato `db.write_prices(df, ticker)`.
FR13: [Sistema] gera snapshot CSV(s) a partir de dados persistidos e salva em `snapshots/` com checksum SHA256.
FR14: [Usuário/CLI] pode exportar dados persistidos para CSV/JSON a pedido.
FR15: [Sistema] registra metadados do snapshot (created_at, rows, checksum) em `metadata` ou `snapshots` table.
FR16: [Usuário/CLI] pode executar `poetry run main --ticker <TICKER> [--force-refresh]` para quickstart end‑to‑end.
FR17: [Usuário/CLI] pode executar subcomando `--test-conn --provider <name> --health`.
FR18: [Administrador] pode listar histórico de ingestões e status via comando operacional.
FR19: [Usuário] pode abrir notebook parametrizável que consome `dados/data.db` para um ticker fornecido.
FR20: [Usuário] pode executar notebook quickstart e gerar gráficos comparativos (prices/returns).
FR21: [Sistema] fornece rotina que transforma preços em returns diários e grava em `returns`.
FR22: [Usuário] pode iniciar um POC Streamlit que lê do banco local e exibe gráficos básicos por ticker.
FR23: [Dev/Ops] pode executar POC Streamlit localmente; requisitos de implantação e containerização documentados separadamente.
FR24: [Desenvolvedor/API] pode invocar `portfolio.generate(prices_df, params)` (ou equivalente) e receber pesos + métricas.
FR25: [Sistema] exporta resultados de modelagem em CSV/JSON compatível com consumo por notebooks.
FR26: [CI] executa testes unitários e integração mockada que validam ingest→CSV→checksum fluxo.
FR27: [Desenvolvedor] pode rodar suíte de testes localmente e obter resultados pass/fail claros.
FR28: [Tech Writer] pode adicionar `docs/phase-N-report.md` com checklist, comandos reproducíveis e amostras de CSV para cada fase.
FR29: [Usuário/Dev] encontra no `README` instruções quickstart reproduzíveis para executar o fluxo end‑to‑end.
FR30: [Sistema] registra `ingest_logs` com (ticker, started_at, finished_at, rows_fetched, status, error_message).
FR31: [Administrador] pode consultar logs para diagnosticar falhas de ingest.
FR32: [Sistema/DevOps] aplica permissões de arquivo para `dados/data.db` (owner-only) por padrão local.
FR33: [Desenvolvedor] encontra orientações em docs para gerenciar credenciais via `.env` sem comitar segredos.
FR34: [Sistema] mantém `schema_version` e aplica migrações controladas ao DB (migrations traceáveis).
FR35: [Sistema] suporta provedores via interface pluggable (adicionar/remover providers sem alterar core logic).
FR36: [Sistema] executa retries com backoff configurável ao recuperar dados de provedores e registra tentativas em `ingest_logs`.
FR37: [CI] valida que qualquer CSV gerado inclua checksum SHA256; job CI verifica o checksum e falha em caso de mismatch.
FR38: [Docs] `docs/phase-1-report.md` contém comando quickstart completo, checklist de aceitação e amostra de CSV com cabeçalho e metadados.
FR39: [Administrador] pode consultar métricas de ingestão e telemetria (jobs por ticker, latência, taxas de erro) via comando ou relatório.
FR40: [Sistema/Operador] realiza backups agendados do arquivo `dados/data.db` e permite restauração testada.
FR41: [Desenvolvedor/Operador] aplica migrações de esquema versionadas que suportam rollback seguro.
FR42: [Sistema] garante execução concorrente segura por ticker (um job por ticker por vez) para evitar corrupção em SQLite.
FR43: [Process/Owner: Tech Writer/PM] garantir que requisitos ambíguos sejam reformulados no formato "[Actor] pode [capability]" e mapeados a critérios curtos de aceitação.

### NonFunctional Requirements

NFR-P1: Quickstart end‑to‑end (`poetry run main --ticker <TICKER> --force-refresh`) completa em ≤ 30 minutos em máquina dev típica.
NFR-P2: Comando de healthcheck/metrics responde em < 5s sob carga normal (ex.: sem ingest concorrente pesado).
NFR-P3: Geração de snapshot CSV para um ticker com até 10 anos de dados diários conclui em < 2 minutos em máquina dev típica.
NFR-R1: Ingests falhos executam retry exponencial com até 3 tentativas; falhas são registradas em `ingest_logs` com motivo.
NFR-R2: Backups de `dados/data.db` podem ser feitos manualmente e agendados; rotina de restauração deve ser testada regularmente.
NFR-O1: Sistema exporta logs estruturados (JSON) com campos mínimos: `ticker`, `job_id`, `started_at`, `finished_at`, `rows_fetched`, `status`, `error_message`, `duration_ms`.
NFR-O2: Métricas básicas (jobs por ticker, latência média, taxa de erro por fonte) estão disponíveis via comando `main --metrics`.
NFR-S1: O sistema garante execução concorrente segura por ticker (um job por ticker por vez); tentativas concorrentes são enfileiradas ou rejeitadas e logadas.
NFR-S2: Projeto deve permitir extensão para batch/multi‑ticker sem comprometer integridade do SQLite (documentado como limite operacional).
NFR-Sec1: Por padrão, o arquivo `dados/data.db` tem permissões owner-only (ex.: `chmod 600`) após criação.
NFR-M1: Migrações de esquema são versionadas e suportam rollback seguro (`migrations status` / `migrations apply` / `migrations rollback`).
NFR-M2: CI executa testes unitários e de integração, e falha se geração de CSV ou checksum estiver incorreta.
NFR-INT1: Adaptadores de provedores implementam interface estável e documentada com retries configuráveis e logging de rate limits.

### Additional Requirements

- Starter template: Python lightweight starter (Poetry + Typer + pandas + SQLAlchemy + Streamlit + pytest + black/ruff + python-dotenv).
- Use SQLAlchemy for DB abstraction and `pandas` for ETL; implement `Adapter -> Canonical Mapper` layer.
- Persist raw responses in `raw/<provider>/` and record `raw_checksum` (SHA256) for auditability.
- Implement canonical mapping per provider and document mappings in `docs/planning-artifacts/adapter-mappings.md`.
- Observability: JSON-structured logs, metrics (`job_latency`, `rows_fetched`, `error_rate`), and CLI `--metrics`.
- Upsert semantics: `INSERT OR REPLACE` / `ON CONFLICT` by `(ticker, date)` to ensure idempotency.
- Migrations: start with simple scripts and table `schema_version`; evaluate `alembic` in Phase 3.
- Testing: mock providers in CI for quickstart integration; add unit tests for adapters and DB upsert.
- Validation: use `pandera` for DataFrame validation and `pydantic` for configs/DTOs.
- Security: do not commit secrets; provide `.env.example` and recommend `python-dotenv` for local dev.
- Backup & restore commands + runbook for operations.
- Starter CLI: Typer-based entrypoints (e.g., `pipeline.ingest`, `db.*`, `snapshots`).

### FR Coverage Map

FR1: Epic 1 - Ingestão e validação por ticker
FR2: Epic 1 - Adaptadores críticos integrados (Yahoo, AlphaVantage)
FR3: Epic 1 - Suporte a múltiplos provedores (nível mínimo para ingest)
FR4: Epic 1 - Persistência de raw responses
FR5: Epic 1 - Metadados ao persistir dados brutos
FR6: Epic 1 - Validação de estrutura CSV (schema)
FR7: Epic 1 - Flagging e logs de validação
FR8: Epic 1 - Relatório de validação amostra
FR9: Epic 1 - Persistência canônica em SQLite
FR10: Epic 1 - Upsert por (ticker,date)
FR11: Epic 1 - API `db.read_prices`
FR12: Epic 1 - API `db.write_prices`
FR13: Epic 2 - Geração de snapshots CSV com checksum
FR14: Epic 2 - Exportação CSV/JSON
FR15: Epic 2 - Metadados de snapshot registrados
FR16: Epic 3 - Quickstart CLI end-to-end
FR17: Epic 3 - Subcomando health/test-conn
FR18: Epic 4 - Operações: listar histórico e status
FR19: Epic 3 - Notebooks parametrizáveis
FR20: Epic 3 - Execução de notebooks quickstart
FR21: Epic 1 - Transformação de preços em returns
FR22: Epic 3 - Streamlit POC
FR23: Epic 3 - Execução local do POC Streamlit
FR24: Epic 6 - `portfolio.generate` POC
FR25: Epic 6 - Exportação de resultados de modelagem
FR26: Epic 0 - CI inicial e pipeline de testes
FR27: Epic 0 - Suporte a execução local de testes (dev)
FR28: Epic 0 - Documentação inicial / phase-N reports
FR29: Epic 0 - README e quickstart reproducível (ownership consolidado)
FR30: Epic 4 - `ingest_logs` e telemetria
FR31: Epic 4 - Consulta de logs para diagnóstico
FR32: Epic 8 - Permissões de `dados/data.db`
FR33: Epic 8 - Gestão de segredos e `.env.example`
FR34: Epic 7 - Script de versionamento de schema (`schema_version`)
FR35: Epic 5 - Interface pluggable de providers
FR36: Epic 1 - Retries com backoff configurável
FR37: Epic 2 - CI validação de checksum em CSVs
FR38: Epic 2 - Exemplos de quickstart em docs/phase-1-report.md
FR39: Epic 4 - Métricas e telemetria acessíveis via CLI
FR40: Epic 4 - Backup agendado e restauração testada
FR41: Epic 7 - Migrações de esquema versionadas e rollback
FR42: Epic 1 - Concorrência segura por ticker (operacional)
FR43: Epic 7 - Garantir requisitos documentais e reformulação de requisitos ambíguos

## Epic List

### Epic 0 — Preparação do Ambiente de Desenvolvimento
Objetivo: Fornecer o esqueleto do projeto, configurações de desenvolvimento, CI inicial, `pyproject.toml`, `README` quickstart, `pre-commit` e exemplos de fixtures para que desenvolvedores consigam rodar e contribuir rapidamente.
**FRs covered:** FR26, FR27, FR28, FR29

### Story 0.1: Inicializar `pyproject.toml` e dependências mínimas

As a Developer,
I want a minimal `pyproject.toml` with declared dependencies and dev-dependencies,
So that I can install and run the project and tests consistently using `poetry`.

**Acceptance Criteria:**

**Given** a clean checkout of the repository
**When** I run `poetry install` (or `poetry install --no-dev` for CI)
**Then** the runtime and dev dependencies are installed without errors
**And** `poetry run main --help` (or `python -m src.main --help`) shows the CLI help output
**And** `pyproject.toml` contains pinned/minimal versions for key packages (e.g., `pandas`, `sqlalchemy`, `typer`, `pytest`) documented in the file

### Story 0.2: Criar `README.md` Quickstart

As a New Contributor,
I want a concise `README.md` quickstart with required commands,
So that I can reproduce the quickstart experiment in ≤ 30 minutes.

**Acceptance Criteria:**

**Given** a developer on a fresh machine with Python 3.12 and Poetry
**When** they follow the README quickstart steps
**Then** they can run `poetry install` and `poetry run main --help` and execute a sample quickstart command
**And** the README lists example tickers and expected output locations (`snapshots/`, `dados/`).

### Story 0.3: Adicionar `pre-commit` com `black` e `ruff`

As a Maintainer,
I want `pre-commit` hooks configured for code style and linting,
So that commits enforce consistent formatting and basic lint rules.

**Acceptance Criteria:**

**Given** the repository with `.pre-commit-config.yaml`
**When** a contributor makes a commit
**Then** `pre-commit` runs `black` and `ruff` and prevents commit on failures
**And** documentation in README explains how to install and run `pre-commit` locally.

### Story 0.4: Criar skeleton de CI (`.github/workflows/ci.yml`)

As a CI Engineer,
I want a GitHub Actions workflow that runs install + tests + lint,
So that pull requests verify project health automatically.

**Acceptance Criteria:**

**Given** a push or PR to any branch
**When** GitHub Actions runs the `ci.yml`
**Then** it runs a lightweight CI matrix (Python 3.12) with steps:

- `poetry install --no-dev` (install runtime deps for quick smoke)
- `poetry install` (install dev deps)
- `poetry run pytest -q --maxfail=1`
- `ruff . --select` and `black --check .`

**And** the workflow reports pass/fail in the PR status and artifacts/logs are available for failures.

### Story 0.5: Adicionar fixtures de teste e exemplo de dados (amostra)

As a Test Author,
I want example pytest fixtures and a small sample CSV for a ticker,
So that unit and integration tests can run deterministically and quickly.

**Acceptance Criteria:**

**Given** tests that rely on fixture data
**When** pytest is executed
**Then** tests use an in-repo sample CSV and SQLite in-memory fixtures and pass deterministically
**And** sample CSV is small (< 100 rows), added at `tests/fixtures/sample_ticker.csv`, and documented in `tests/fixtures/README.md`.

**And** `tests/conftest.py` exposes a fixture that loads `tests/fixtures/sample_ticker.csv` into an in-memory SQLite database for tests.

### Story 0.6: Criar `.env.example` e instruções de configuração local

As a Developer,
I want a `.env.example` and clear instructions to set env vars locally,
So that I can configure API keys and local paths without committing secrets.

**Acceptance Criteria:**

**Given** the repository
**When** a developer copies `.env.example` to `.env` and fills placeholder values
**Then** the project reads `.env` optionally (via `python-dotenv`) for local runs
**And** README explains which variables are required and which are optional.

**Notes for `.env.example`:**
- `YF_API_KEY=` (optional; provider-specific)
- `DATA_DIR=./dados`
- `SNAPSHOT_DIR=./snapshots`
- `LOG_LEVEL=INFO`

The README must include a short snippet demonstrating using `python-dotenv` (or `poetry run main` reading env) and a reminder to never commit real secrets.

### Story 0.7: Teste de integração quickstart (mocked) e passo de CI para validação de checksum

As a CI Engineer / Developer,
I want a mocked integration test that runs the quickstart and a CI step that validates snapshot checksums,
So that PRs validate end-to-end snapshot generation and checksum correctness without network access.

**Acceptance Criteria:**

- **Given** a CI environment with fixtures,
- **When** the CI runs the integration test for quickstart (mocked providers),
- **Then** a snapshot CSV is generated and the CI step computes the SHA256 checksum and compares it with the expected value; the job fails on mismatch.
- The CI workflow is defined in `.github/workflows/ci.yml` and includes an artifact publishing step for the generated CSV and its `.checksum` file.

**FRs referenced:** FR16, FR37

**Estimate:** 3 SP

**Owner:** Dev / CI

---

### Story 0.8: Playbooks quickstart e UX minimal (`docs/playbooks/quickstart-ticker.md`, `docs/playbooks/ux.md`)

As a PM / Tech Writer,
I want a concise quickstart playbook and a minimal UX playbook describing CLI flags, notebook params and Streamlit screens,
So that contributors and users can reproduce experiments and understand expected UI/CLI behavior.

**Acceptance Criteria:**

- **Given** a developer or user,
- **When** they follow `docs/playbooks/quickstart-ticker.md`,
- **Then** they can reproduce the ingest→persist→snapshot→notebook flow in ≤ 30 minutes using the documented commands and examples.
- `docs/playbooks/ux.md` documents expected CLI messages, success/error messaging, notebook parameter names and Streamlit minimal screens.

**FRs referenced:** FR29, FR19, FR22

**Estimate:** 2 SP

**Owner:** PM / Tech Writer



### Epic 1 — Ingestão e Persistência
Objetivo: Permitir ao usuário ingerir um ticker, validar, normalizar e persistir dados no SQLite com idempotência e metadados auditáveis. Inclui o trabalho crítico de adaptadores necessário para que ingest funcione end‑to‑end (Yahoo/AlphaVantage minimal).
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR7, FR8, FR9, FR10, FR11, FR12, FR21, FR35, FR36, FR42

### Story 1.1: Implementar interface de Adapter e adaptador `yfinance` mínimo

As a Developer,
I want a minimal Adapter interface and a working `yfinance` adapter that returns a raw `pandas.DataFrame`,
So that the ingest pipeline can fetch price data for a ticker from a provider.

**Acceptance Criteria:**

**Given** the Adapter interface is defined (`Adapter.fetch(ticker) -> pd.DataFrame`)
**When** the developer invokes the `yfinance` adapter with a sample ticker (e.g., PETR4.SA)
**Then** the adapter returns a `DataFrame` with raw provider columns and a `source` metadata field
**And** the adapter includes basic error handling and returns descriptive errors for failures.
**And** the adapter documentation includes expected output schema and the error codes/messages contract.
**FRs referenced:** FR2, FR3

### Story 1.2: Implementar Canonical Mapper (Provider -> Schema canônico)

As a Developer,
I want a canonical mapper that normalizes provider `DataFrame`s to the project's canonical schema,
So that downstream modules can rely on a consistent format for persistence and processing.

**Acceptance Criteria:**

**Given** a raw `DataFrame` from `yfinance` adapter
**When** the canonical mapper is executed
**Then** it returns a `DataFrame` with canonical columns (`ticker`, `date`, `open`, `high`, `low`, `close`, `volume`, `source`, `fetched_at`).
**Nota:** o mapper pode opcionalmente emitir `adj_close` para cálculos internos (ex.: retornos), porém o esquema persistido é definido por `docs/schema.json` e não inclui `adj_close` por padrão. Atualize `docs/schema.json` para persistir `adj_close` quando necessário e siga o processo de versionamento/migração.
**And** it computes `raw_checksum` for the raw payload and includes it in the metadata.
**And** `fetched_at` is normalized to UTC ISO8601 and date handling (timezones) is explicitly documented.
**And** the mapper includes a lightweight `pandera` schema for validation in the canonical step.
**FRs referenced:** FR5, FR35

### Story 1.3: Implementar comando `pipeline.ingest` (orquestrador básico)

As a User (CLI),
I want a `pipeline.ingest --ticker <TICKER> --source yfinance` command,
So that I can trigger an end-to-end ingest using the minimal adapter and mapper.

**Acceptance Criteria:**

**Given** the `yfinance` adapter and canonical mapper are available
**When** the user runs `pipeline.ingest --ticker PETR4.SA --source yfinance`
**Then** the pipeline fetches raw data via adapter, normalizes via mapper, saves raw CSV (story 1.4) and persists canonical rows to DB (story 1.6) when those are implemented
**And** the command returns a success/failure exit code and logs a job_id.
**And** the CLI supports flags `--dry-run` (no writes) and `--force-refresh` (ignore cache) for operational control.
**FRs referenced:** FR1, FR11, FR12

### Story 1.4: Salvar resposta bruta em `raw/<provider>/` e registrar metadados

As an Operator,
I want every ingest to save the provider's raw CSV under `raw/<provider>/<ticker>-<ts>.csv` and record `raw_checksum` and `fetched_at`,
So that we can audit and reprocess raw inputs when needed.

**Acceptance Criteria:**

**Given** the pipeline retrieved a raw `DataFrame`
**When** the pipeline persists raw output
**Then** a CSV file is created under `raw/<provider>/` with filename containing ticker and timestamp using the pattern: `<provider>/<ticker>-YYYYMMDDTHHMMSSZ.csv` (UTC timestamp)
**And** created files are written with owner-only permissions by default (e.g., `chmod 600` for DB files and recommended perms for raw files documented)
**And** a metadata record (job_id, source, fetched_at, raw_checksum, rows) is logged to `ingest_logs` (or a staging location) for auditability.
**FRs referenced:** FR4, FR5, FR30

### Story 1.5: Validar estrutura CSV e filtrar/flag rows inválidas

As a Data Engineer,
I want the pipeline to validate incoming CSVs against a minimal schema and flag invalid rows,
So that only valid rows enter the canonical pipeline and invalid rows are traceable.

**Acceptance Criteria:**

**Given** a raw `DataFrame` from the adapter
**When** the validator runs
**Then** rows not matching the schema are flagged and written to `ingest_logs` with reason codes
**And** a validation summary (rows_valid, rows_invalid) is returned and logged.
**And** the pipeline aborts the ingest if invalid rows exceed a default tolerance threshold of 10% (configurable via env var `VALIDATION_INVALID_PERCENT_THRESHOLD`).
**FRs referenced:** FR6, FR7, FR8, FR30

### Story 1.6: Persistir dados canônicos no SQLite com upsert por (ticker,date)

As a Developer,
I want a DB layer that writes canonical rows to `dados/data.db` with idempotent upsert semantics,
So that repeated ingests do not create duplicate records and the database remains consistent.

**Acceptance Criteria:**

**Given** a canonical `DataFrame`
**When** the DB layer writes rows
**Then** rows are upserted by `(ticker, date)` and the `prices` table reflects the latest canonical values
**And** `db.read_prices(ticker, start, end)` returns expected rows for queries.
**And** writes record the current `schema_version` in metadata for traceability.
**FRs referenced:** FR9, FR10, FR11, FR12

### Story 1.7: Implementar transformação de retornos e persistência em `returns`

As a Data Consumer,
I want a routine that computes daily returns from prices and persists them in the `returns` table,
So that downstream notebooks and modeling code can read precomputed returns.

**Acceptance Criteria:**

**Given** canonical `prices` stored in DB
**When** the `compute_returns()` routine runs for a ticker
**Then** daily returns are computed (simple pct change) and persisted to `returns` with `return_type='daily'`
**And** annualization conventions (252 days) are documented in code/comments.
**FRs referenced:** FR21

### Story 1.8: Implementar retries/backoff no adaptador crítico

As an Operator,
I want adapter calls to use a configurable retry policy with exponential backoff,
So that transient provider errors are retried automatically and logged.

**Acceptance Criteria:**

**Given** the adapter performs an HTTP request or network call
**When** transient errors (5xx, timeouts) occur
**Then** the adapter retries up to N attempts with exponential backoff and logs each retry attempt
**And** a failure after retries records the error in `ingest_logs`.
**And** defaults are: `ADAPTER_MAX_RETRIES=3` and exponential backoff with jitter; the max retries is configurable via env var `ADAPTER_MAX_RETRIES`.
**FRs referenced:** FR36, FR30

### Story 1.9: Garantir execução concorrente segura por ticker (lock simples)

As an Operator,
I want the ingest pipeline to prevent concurrent ingests for the same ticker (simple lock),
So that we avoid contention and potential SQLite corruption.

**Acceptance Criteria:**

**Given** two concurrent `pipeline.ingest --ticker PETR4.SA` requests
**When** both start within a small window
**Then** the pipeline allows one to run and the other either waits or exits with a clear message (configurable behavior)
**And** the behavior is logged to `ingest_logs`.
**And** the default locking strategy is a filesystem-based lock with default behavior `wait` and timeout of 120 seconds (configurable via `INGEST_LOCK_TIMEOUT_SECONDS`).
**FRs referenced:** FR42, FR30

### Story 1.10: Cache de snapshots e ingestão incremental

As a Developer,
I want snapshot caching with an incremental ingest mode that only appends novos dados,
So that repeated runs are fast and minimize API hits and compute.

**Acceptance Criteria:**

- **Given** an existing snapshot CSV for a ticker with last date D,
- **When** the ingest runs in `--incremental` mode,
- **Then** the pipeline fetches only data after D, appends new rows to the CSV and updates the snapshot checksum.
- Cache metadata is stored (last_timestamp, row_count, checksum) in `snapshots/metadata.json` or similar and used to short-circuit full-fetch runs.

**FRs referenced:** FR10, FR13

**Estimate:** 3 SP

**Owner:** Dev

---

### Story 1.11: Definir esquema canônico de dados e documentação do modelo (schema + examples)

As a Data Engineer / Tech Writer,
I want a canonical schema for stored CSV snapshots and a documented example file,
So that downstream consumers (notebooks, metrics) have a stable contract.

**Acceptance Criteria:**

- A `schema.yaml` (or `schema.json`) defines column names, types, nullable flags and semantic notes (ex: `Adj Close` is float, `Return` is decimal percents).
- An example CSV `dados/examples/ticker_example.csv` is included and referenced by `docs/schema.md` explaining column meanings and versioning strategy.
- Migration notes for schema changes are documented (minor vs breaking changes) and versioned using `schema_version` in snapshot metadata.

**FRs referenced:** FR05, FR07

**Estimate:** 2 SP

**Owner:** Data / Tech Writer


### Epic 2 — Snapshots & Exportação
Objetivo: Gerar snapshots CSV com checksum SHA256, expor metadados e garantir verificação automatizada (CI) dos arquivos gerados.
**FRs covered:** FR13, FR14, FR15, FR37, FR38

### Story 2.1: Gerar snapshot CSV a partir de dados persistidos

As a User,
I want the system to generate a snapshot CSV for a ticker from the canonical `prices` table,
So that I can export a stable copy of the data for analysis and archival.

**Acceptance Criteria:**

**Given** canonical `prices` exist in `dados/data.db` for a ticker
**When** the user runs `pipeline.snapshot --ticker PETR4.SA --date 2026-02-15`
**Then** a CSV is written to `snapshots/<ticker>-YYYYMMDD.csv` containing the canonical rows for that date range
**And** snapshot metadata (created_at, rows, source_version) is returned.
**FRs referenced:** FR13, FR15

### Story 2.2: Calcular SHA256 e registrar metadados do snapshot

As an Operator,
I want the snapshot process to compute a SHA256 checksum for each generated CSV and store metadata,
So that CI and downstream processes can verify snapshot integrity.

**Acceptance Criteria:**

**Given** a snapshot CSV is generated
**When** the snapshot finalization step runs
**Then** a SHA256 checksum is computed and recorded in the `snapshots` metadata table (created_at, rows, checksum, job_id)
**And** the checksum file or metadata is stored alongside the CSV.
**FRs referenced:** FR13, FR15, FR37

### Story 2.3: Exportar snapshot como CSV/JSON via CLI/API

As a Developer/User,
I want a CLI command and programmatic function to export persisted data as CSV or JSON,
So that consumers can obtain the snapshot in the desired format.

**Acceptance Criteria:**

**Given** data persisted for a ticker
**When** the user runs `pipeline.export --ticker PETR4.SA --format json --out ./out.json`
**Then** the requested format is produced and stored at the requested path
**And** metadata (rows, checksum if CSV) is produced and printed to stdout or returned by the API.
**FRs referenced:** FR14

### Story 2.4: CI validation job para checar checksums de snapshots

As a CI Engineer,
I want a CI job that validates generated snapshot checksums against recorded metadata,
So that pull requests that touch snapshot generation or schema fail if checksums mismatch in controlled tests.

**Acceptance Criteria:**

**Given** a test snapshot is generated in CI (mocked or small sample)
**When** CI runs the validation step
**Then** the job computes checksum and compares with expected value and fails on mismatch
**And** the job exposes logs/artifacts for failed comparisons.
**FRs referenced:** FR37

### Story 2.5: Política de retenção e purge de snapshots

As an Operator,
I want a configurable retention policy for snapshots (e.g., keep last N or keep last X days),
So that storage is managed and old snapshots are pruned automatically.

**Acceptance Criteria:**

**Given** snapshots older than retention policy exist
**When** the retention job runs (`pipeline.snapshot --purge` or scheduled)
**Then** snapshots outside the retention policy are deleted and metadata updated
**And** deletions are logged with job_id and affected files.
**FRs referenced:** FR40, FR13

### Story 2.6: Verificação de restauração a partir de snapshot

As a Developer/Operator,
I want a verification routine that restores a DB slice from a snapshot and runs basic integrity checks,
So that we can validate that snapshots can be used to recover data.

**Acceptance Criteria:**

**Given** a snapshot CSV file
**When** the restore verification runs into a temporary DB
**Then** the restored DB has expected row counts and checksums match
**And** the verification returns pass/fail and logs details.
**FRs referenced:** FR13, FR15

### Epic 3 — Quickstart CLI & Notebooks
Objetivo: Entregar o fluxo quickstart (`poetry run main --ticker ...`), notebooks parametrizáveis e POC Streamlit para que usuários reproduzam experimentos em ambiente dev.
**FRs covered:** FR16, FR17, FR19, FR20, FR22, FR23, FR29

### Story 3.1: Implementar Quickstart CLI end‑to‑end

As a New User,
I want a single command `poetry run main --ticker <TICKER> [--force-refresh]` that executes ingest→persist→snapshot→notebook-run (where applicable),
So that I can reproduce a complete experiment quickly.

**Acceptance Criteria:**

**Given** a developer machine with dependencies installed
**When** the user runs `poetry run main --ticker PETR4.SA --force-refresh`
**Then** the pipeline executes ingest (using adapter), persists canonical data, generates snapshot CSV, and returns a success status
**And** a short summary with job_id, elapsed time, snapshot path and rows is printed to stdout
**And** a short summary with job_id, elapsed time, snapshot path and rows is printed to stdout

**Notes from Party Mode review (applied):**

- CLI must support operational flags: `--dry-run` (no writes), `--no-network` (use fixtures/mocks), `--sample-tickers <file|list>`, `--max-days <N>`, and `--format json|text`.
- CLI should print an example JSON summary when `--format json` is used. Example expected output for CI/smoke with fixtures:

  ```json
  {"job_id":"<uuid>","elapsed_sec":12,"snapshot":"snapshots/PETR4-20260215.csv","rows":42}
  ```

- The CLI must return semantically meaningful exit codes (0=OK, 1=Warning, 2=Critical) to allow CI checks.
- CI smoke tests should run `poetry run main --no-network --ticker PETR4.SA` and expect `exit code 0` and a JSON summary when `--format json` is provided.

**FRs referenced:** FR16, FR13, FR9

### Story 3.2: Notebooks parametrizáveis e quickstart notebook

As a Researcher,
I want notebooks that accept parameters (ticker, date range) and read from `dados/data.db`,
So that I can reproduce visualizations and analyses for any ticker.

**Acceptance Criteria:**

**Given** canonical `prices` exist for a ticker
**When** the user opens `notebooks/quickstart.ipynb` with parameters set
**Then** the notebook loads data from DB, computes returns and renders example plots (prices vs returns)
**And** the notebook includes a cell that demonstrates `snapshot` loading and checksum verification.
**FRs referenced:** FR19, FR20

**Notes from Party Mode review (applied):**

- Notebooks must be parametrizáveis e reprodutíveis via `papermill`. Ex.: `papermill notebooks/quickstart.ipynb notebooks/out.ipynb -p ticker PETR4.SA -p start 2020-01-01 -p end 2026-02-15`.
- Adicionar `notebooks/requirements.txt` e um alvo `make notebook-run` no `Makefile` para facilitar execução local e em CI (quando aplicável).
- Documentar pré-requisitos do kernel e instruções de reproducibilidade no topo do notebook.

### Story 3.3: Streamlit POC básico que consome o DB

As a Productive User,
I want a Streamlit app that reads a ticker from `dados/data.db` and displays basic charts,
So that non-technical users can interactively explore data.

**Acceptance Criteria:**

**Given** the Streamlit app is started (`poetry run streamlit run src/apps/streamlit_poc.py`)
**When** the user selects a ticker and date range
**Then** the app displays price and returns charts and an option to download the snapshot CSV
**And** the app reads from the local DB only and includes a toggle to use cached snapshot or re-run ingest (if allowed).
**FRs referenced:** FR22, FR23

**Notes from Party Mode review (applied):**

- The POC must include a `use-mock-data` toggle (accessible via UI and a `--use-mock-data` env/config) to avoid external calls during demos and CI.
- The Streamlit POC must isolate its backend access to a local/cached API layer so demos do not call real providers or require API keys.
- Do not run the Streamlit UI in CI; CI should only run linters/build steps for the app.

### Story 3.4: CLI health/metrics commands (`--metrics`, `--test-conn`)

As an Operator,
I want CLI commands to show health and basic metrics (`poetry run main --metrics`, `poetry run main --test-conn --provider yfinance`),
So that I can quickly inspect system health and provider connectivity.

**Acceptance Criteria:**

**Given** the system has run at least one ingest
**When** the user runs `poetry run main --metrics`
**Then** basic metrics (last ingest per ticker, job latency, rows_fetched, error counts) are printed
**And** `poetry run main --test-conn --provider yfinance` performs a light connectivity check and returns status.
**FRs referenced:** FR17, FR30, NFR-O2

**Notes from Party Mode review (applied):**

- Metrics and health commands must support `--format json` for machine parsing and should return semantic exit codes (0=OK,1=Warning,2=Critical).
- Recommended commands to implement: `main metrics ingest-lag`, `main metrics last-date <ticker>`, `main test-conn --provider <name>`; each should document expected JSON schema for `--format json`.

### Story 3.5: Quickstart examples and reproducible scripts

As a New Contributor,
I want example scripts and commands that reproduce the quickstart for sample tickers,
So that I can validate the environment and understand expected outputs.

**Acceptance Criteria:**

**Given** a fresh checkout and dependencies installed
**When** the developer runs `examples/run_quickstart_example.sh`
**Then** the example executes the quickstart for a sample ticker, generates a snapshot in `snapshots/` and writes a short run log to `logs/`.
**And** the example script documents expected run time and outputs in comments.
**FRs referenced:** FR29, FR16

**Notes from Party Mode review (applied):**

- Example scripts must accept `--config` or respect `ENV` vars and write logs to `logs/` and artifacts to `outputs/` by default.
- Provide `examples/run_quickstart_example.sh` that executes `poetry run main --no-network --ticker PETR4.SA --format json --sample-tickers tests/fixtures/sample_ticker.csv` and exits with non-zero on failures to allow CI to detect regressions.

### Story 3.6: Documentar expected outputs e paths no README e notebooks

As a Tech Writer,
I want a clear section in README and notebook header that documents expected output locations (`snapshots/`, `dados/`, `raw/`) and example filenames,
So that users immediately know where to look for generated artifacts.

**Acceptance Criteria:**

**Given** the quickstart is executed
**When** the user reads README and notebook header
**Then** they find explicit paths, filename patterns, and a sample output snippet showing a CSV header and checksum line.
**FRs referenced:** FR29, FR13

**Notes from Party Mode review (applied):**

- README quickstart must include a copy-paste command and an expected JSON/text short summary example (see Story 3.1) and an example CSV header plus checksum line, e.g.:

  ```csv
  date,open,high,low,close,volume
  2026-02-14,10.0,10.5,9.8,10.2,100000
  # checksum: sha256:<hex>
  ```

- Add a short troubleshooting section indicating common failure modes and where to find logs (`logs/`) and outputs (`outputs/`, `snapshots/`).

### Epic 4 — Operações & Observabilidade
Objetivo: Oferecer ferramentas operacionais e observabilidade: logs estruturados, métricas, healthchecks, backup/restore e comandos operacionais.
**FRs covered:** FR18, FR30, FR31, FR39, FR40

### Story 4.1: Implementar CLI de métricas e health

As an Operator,
I want CLI commands that expose basic metrics and health status,
So that I can quickly assess system health and automate checks in CI.

**Acceptance Criteria:**

**Given** the system has run at least one ingest
**When** the operator runs `poetry run main metrics` or `poetry run main --metrics --format json`
**Then** the CLI prints metrics (last ingest per ticker, ingest-lag, job latency averages, rows_fetched, error counts) in human-readable or JSON format
**And** the command exits with semantic codes (0=OK, 1=Warning, 2=Critical) depending on thresholds (e.g., ingest-lag > 24h → exit 2)
**And** `poetry run main test-conn --provider <name>` returns connectivity status and latency for a lightweight provider check.
**And** the CLI supports an environment variable `METRICS_INGEST_LAG_THRESHOLD` (default `86400`) to drive severity thresholds used for exit codes.
**And** the `--format json` output conforms to the documented JSON schema in this file (fields: `ticker`, `last_ingest`, `ingest_lag_seconds`, `job_latency_ms`, `rows_fetched`, `error_count`).
**And** the CLI exposes subcommands `metrics ingest-lag` and `metrics last-date <ticker>` and supports pagination for large outputs where applicable.

**FRs referenced:** FR17, FR18, FR30, NFR-O2

### Story 4.2: Logs estruturados e busca de ingest_logs

As an Operator/Developer,
I want structured JSON logs and CLI to query `ingest_logs`,
So that failures and historical ingest activity can be audited and traced.

**Acceptance Criteria:**

**Given** ingests have been executed and `ingest_logs` populated
**When** the operator runs `poetry run main logs --ticker PETR4.SA --since 2026-02-01 --format json`
**Then** the CLI returns structured JSON log entries with fields (`ticker`, `job_id`, `started_at`, `finished_at`, `rows_fetched`, `status`, `error_message`, `duration_ms`)
**And** a query for failures returns non-zero exit code and a short summary to stdout.
**And** the CLI accepts pagination flags `--limit <N>` and `--offset <N>` for large result sets.
**And** logs are structured JSON including `job_id`, `provider` (if applicable), `attempt`, `status_code`, `retry_after` (nullable) and `duration_ms` to enable correlation.

**FRs referenced:** FR30, FR31, NFR-O1

### Story 4.3: Backup & Restore operacional

As an Operator,
I want commands to create and restore backups of `dados/data.db` and verify integrity,
So that I can perform recoveries and validate backups in test runs.

**Acceptance Criteria:**

**Given** the system has canonical data in `dados/data.db`
**When** the operator runs `poetry run main backup --create --out backups/backup-20260215.db` or `poetry run main backup --restore --from backups/backup-20260215.db`
**Then** the backup is created (copied) and the restore verification routine loads the backup into a temporary DB and runs basic integrity checks (row counts, checksum match)
**And** backup/restore operations are logged with job_id and reported in the CLI summary.
- **And** backups are created atomically (write-to-temp + rename) and a checksum (SHA256) is computed and written to a companion `.checksum` file.
- **And** created backup files receive owner-only permissions (`chmod 600`) by default after creation.
- **And** the `backup --create` command supports `--verify` which runs the restore verification automatically and returns non-zero on verification failure.

**FRs referenced:** FR40, FR15

### Story 4.4: Monitoramento de integridade de snapshots (CI)

As a CI Engineer,
I want a job that validates snapshot checksums and alerts on mismatch,
So that snapshot generation/regressions are detected early in PRs.

**Acceptance Criteria:**

**Given** a snapshot CSV is generated in CI (mocked or sample)
**When** the CI validation job runs
**Then** it computes the SHA256 checksum and compares with the recorded metadata and fails the job on mismatch
**And** the job publishes an artifact with the computed checksum and a short failure report.

**And** the CI validation job publishes both the generated CSV and a `.checksum` artifact when run, and the job fails on checksum mismatch.
**And** the CI job can run in `--no-network` mode using deterministic fixtures under `tests/fixtures/` to compute the expected checksum.

**FRs referenced:** FR37, FR13

### Story 4.5: Integração simples de alerting e thresholds operacionais

As an Operator,
I want simple alert rules (scripted) for key thresholds (ingest-lag, high error-rate),
So that I am notified when operational SLAs are violated.

**Acceptance Criteria:**

**Given** metrics are available from `main metrics`
**When** ingest-lag > configurable threshold (default 24h) or error-rate > configurable threshold
**Then** an alert script emits a standardized message to stdout and exits with code 2 (or triggers an external webhook if configured)
**And** alerting rules are documented in `docs/operations/alerts.md` with suggested thresholds and runbook.

**FRs referenced:** FR39, NFR-O1

### Story 4.6: Health checks and readiness probes for local deployments

As a DevOps/Operator,
I want lightweight health and readiness probes,
So that local deployments (or containerized POCs) can be checked programmatically.

**Acceptance Criteria:**

**Given** a local service or container exposing the CLI or a small HTTP probe
**When** `poetry run main --health` or `curl http://localhost:8000/health` is executed
**Then** the probe returns status (ok/warn/critical) and a JSON payload with `uptime`, `last_ingest`, `ingest_lag_seconds`, and `db_accessible` boolean
**And** readiness probe returns non-200 when DB is inaccessible.

**FRs referenced:** FR17, FR30, NFR-P2

### Story 4.7: Runbook e documentação operacional

As an Operator/Tech Writer,
I want a concise operational runbook describing common diagnoses and commands,
So that on-call engineers can follow step-by-step recovery and troubleshooting instructions.

**Acceptance Criteria:**

**Given** the repository
**When** a user opens `docs/operations/runbook.md`
**Then** they find instructions for: checking `ingest_logs`, running `main backup --restore`, interpreting `main metrics`, performing snapshot checksum verification, and escalation paths
**And** the runbook includes example commands and expected outputs for common failure modes.

**FRs referenced:** FR18, FR30, FR31, FR40

### Notas da revisão (Party Mode) — Epic 4

- PM: Aprovação geral; pedir que defaults e exemplos constem no README quickstart para reduzir dúvidas dos contribuintes.
- Arquiteto: Documentar o *JSON schema* para `--format json` e definir thresholds padrão em `ENV` (ex.: `METRICS_INGEST_LAG_THRESHOLD`). Recomenda circuit-breaker simples e policy de retry configurável.
- Dev: Garantir `--no-network`/`--use-fixture` para CI, incluir `job_id` em todos os logs e suportar exit codes semânticos (0/1/2). Implementar atomic backup (write-to-temp + rename) e `chmod 600` após criação.
- QA: Criar testes que simulem ingest-lag, verifiquem schema JSON e exit codes; incluir fixtures determinísticos para validação de checksum em CI.
- Tech Writer: Incluir exemplos de saída JSON e CSV no README; adicionar seção de troubleshooting com comandos copy-paste.

Riscos & recomendações rápidas:

- CI deve rodar sem rede — todas as validações críticas (quickstart, checksum) precisam de fixtures em `tests/fixtures/`.
- Padronizar permissões (`chmod 600`) para DB e backups e documentar isso em Epic 8.
- Publicar artifacts de CSV e `.checksum` em CI para facilitar investigação de falhas.


### Operational defaults, env vars e exemplos (Epic 4)

Recomendações operacionais e exemplos executáveis aplicáveis às histórias 4.1–4.7. Estes valores servem como defaults para desenvolvimento e CI; podem ser sobrescritos por `ENV` ou `--config`.

- Variáveis de ambiente recomendadas (com defaults):

  - `DATA_DIR=./dados`
  - `SNAPSHOT_DIR=./snapshots`
  - `BACKUP_DIR=./backups`
  - `LOG_LEVEL=INFO`
  - `ADAPTER_MAX_RETRIES=3`
  - `VALIDATION_INVALID_PERCENT_THRESHOLD=10`  # percent
  - `INGEST_LOCK_TIMEOUT_SECONDS=120`
  - `METRICS_INGEST_LAG_THRESHOLD=86400`  # seconds (24h)
  - `ALERT_WEBHOOK_URL=` (opcional)
  - `ALERTING_ENABLED=false`

- Exemplo de comando CI/smoke (sem rede) e saída esperada JSON:

  ```bash
  poetry run main --no-network --ticker PETR4.SA --format json
  ```

  Exemplo de saída JSON (esperado em CI/smoke):

  ```json
  {"job_id":"<uuid>","status":"success","elapsed_sec":12,"snapshot":"snapshots/PETR4-20260215.csv","rows":42}
  ```

- Schema JSON recomendado para `main metrics --format json` (mínimo):

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

- Exemplo CSV + checksum (formato esperado para snapshots):

  ```csv
  date,open,high,low,close,volume
  2026-02-14,10.0,10.5,9.8,10.2,100000
  # checksum: sha256:<hex>
  ```

- Permissões e segurança mínimas (sugestão de comando após criação do DB/backup):

  ```bash
  chmod 600 dados/data.db
  chmod 600 backups/backup-20260215.db
  ```

- Observações para CI:

  - Todos os jobs críticos (quickstart, snapshot checksum validation, smoke metrics) devem poder rodar com `--no-network` usando fixtures sob `tests/fixtures/` para evitar chamadas externas.
  - Jobs que validam checksums devem publicar o CSV gerado e um arquivo `.checksum` como artifacts para investigação em falhas.

Adicionar estas recomendações às histórias e ao `docs/operations/runbook.md` garante que implementadores e CI tenham um contrato operacional claro.


### Epic 5 — Adaptadores & Normalização
Objetivo: Implementar adaptadores pluggable para provedores, camada de canonical mapping e persistência de raw responses com mapeamentos documentados. Nota: o trabalho crítico mínimo de adaptadores foi fundido em Epic 1 para viabilizar ingest; Epic 5 foca em expansão e hardening de adaptadores adicionais.
**FRs covered:** (expansão de provedores e mapeamentos adicionais)

### Story 5.1: Refinar interface de Adapter e contrato de provedores

As a Developer,
I want a stable, versioned Adapter interface and contract for providers,
So that new provider implementations can be added without changing core logic.

**Acceptance Criteria:**

**Given** the Adapter interface exists
**When** a new provider is implemented
**Then** it conforms to `Adapter.fetch(ticker) -> pd.DataFrame` with documented metadata fields (`source`, `fetched_at`, `raw_checksum`) and error codes
**And** the interface is versioned (e.g., `Adapter.v1`) with a changelog entry in `docs/planning-artifacts/adapter-mappings.md`.

**FRs referenced:** FR35, NFR-INT1

### Story 5.2: Implementar adaptador AlphaVantage (exemplo adicional)

As a Developer,
I want a working AlphaVantage adapter that returns raw provider DataFrames,
So that the system supports at least two independent providers for redundancy.

**Acceptance Criteria:**

**Given** an API key or `--no-network` fixture
**When** the adapter is invoked for `PETR4.SA`
**Then** it returns a raw `DataFrame` with provider-specific columns and `source='alphavantage'`
**And** the adapter supports retries/backoff (honoring `ADAPTER_MAX_RETRIES`) and logs attempts to `ingest_logs`.

**FRs referenced:** FR2, FR3, FR36

### Story 5.3: Documentar mappings provider→canônico em `adapter-mappings.md`

As a Tech Writer/Dev,
I want a canonical mapping document per provider,
So that implementers know how to translate provider fields into the canonical schema.

**Acceptance Criteria:**

**Given** a provider (e.g., yfinance, alphavantage)
**When** a mapping is documented
**Then** `docs/planning-artifacts/adapter-mappings.md` contains a table with provider column → canonical column mappings, transformation notes (timezone, multipliers) and example raw row → canonical row.

**FRs referenced:** FR35

### Story 5.4: Tratar rate-limits e log de rate-limit por provider

As an Operator/Developer,
I want the adapters to detect and log rate-limit responses and expose retry windows,
So that retries are respectful and observable.

**Acceptance Criteria:**

**Given** a provider responds with rate-limit or 429
**When** the adapter receives it
**Then** it records the event in `ingest_logs` with `retry_after` and `provider_rate_limit=true`
**And** adapters implement exponential backoff with jitter and respect provider `Retry-After` headers when present.

**FRs referenced:** NFR-INT1, FR36

### Story 5.5: Provider contract tests & harness (integration tests)

As a QA/Dev,
I want a test harness and contract tests for adapters,
So that providers conform to expected schema and behavior (retries, error codes, timezones).

**Acceptance Criteria:**

**Given** an adapter implementation
**When** contract tests run (CI or locally)
**Then** they validate: returned columns, presence of `source` and `fetched_at`, proper retries, and deterministic behavior under `--no-network` fixtures
**And** contract tests are runnable via `pytest tests/adapters/test_contract.py` and include a `--provider alpha|yfinance --use-fixture` mode.

**FRs referenced:** FR2, FR35, FR36

### Story 5.6: Expandir Canonical Mapper para suportar provedores adicionais e transformações

As a Developer,
I want the canonical mapper to include provider-specific transformation hooks,
So that differences (timezone, adjusted close handling) are centralized and tested.

**Acceptance Criteria:**

**Given** raw DataFrame(s) from different providers
**When** the canonical mapper executes
**Then** it applies provider-specific hooks to produce identical canonical schema rows for same underlying market data
**And** unit tests demonstrate equivalence for at least one sample ticker between providers using fixtures.

**FRs referenced:** FR5, FR35

### Story 5.7: Provider discovery & configuration

As an Operator/Dev,
I want a provider config YAML that enumerates available providers, priority and per-provider options,
So that adding/removing providers is configuration-driven.

**Acceptance Criteria:**

**Given** `config/providers.yaml`
**When** the pipeline runs
**Then** it reads provider priority, timeouts, API keys (via env) and selects providers according to policy (priority/fallback)
**And** a sample `config/providers.example.yaml` is included in the repo with documented fields.

**FRs referenced:** FR3, FR35

### Notes & Implementation Guidance

- Contract tests must be able to run in CI using `--no-network` by loading fixtures under `tests/fixtures/providers/`.
- Log events for adapters should include `provider`, `attempt`, `status_code`, `retry_after`, and `job_id` for easy correlation.
- Provider-specific mapping examples should be added to `docs/planning-artifacts/adapter-mappings.md` as part of Story 5.3.

### Notas da revisão (Party Mode) — Epic 5

- PM: Priorizar MVP com `yfinance` + `alphavantage` e documentar política de fallback (`config/providers.example.yaml`) para evitar gaps operacionais.
- Arquiteto: Versionar a interface `Adapter` (ex.: `Adapter.v1`) e publicar changelog; provider config deve suportar prioridade, timeouts e circuit-breaker simples.
- Dev: Implementar `--use-fixture`/`--no-network` em adapters; garantir logs com `job_id`, `provider`, `attempt` e `retry_after`; criar loader de `config/providers.yaml` via `pydantic` para validação.
- QA: Criar `tests/adapters/test_contract.py` com modo fixture; validar retries, `fetched_at` timezone e `raw_checksum`; rodar contract tests em CI usando fixtures.
- Tech Writer: Documentar mapeamentos raw→canonical em `docs/planning-artifacts/adapter-mappings.md` com exemplos e checklist "How to add a provider".

Riscos & recomendações rápidas:

- Dependência de provedores externos: mitigar com fixtures e `--no-network` em CI; publicar um small fixture set em `tests/fixtures/providers/`.
- Ambiguidade de timezone/adj_close: exigir transformação explícita no canonical mapper e referências de equivalência nos docs.
- Rate-limits: registrar `retry_after` e respeitar cabeçalhos; expor métricas de rate-limit para monitoramento.



### Epic 6 — Modelagem de Portfólio
Objetivo: Fornecer POC de modelagem (`portfolio.generate`) que retorna pesos e métricas, e exporta resultados para consumo em notebooks.
**FRs covered:** FR24, FR25

### Story 6.1: Implementar `portfolio.generate` POC

As a Researcher/Developer,
I want a minimal `portfolio.generate(prices_df, params)` implementation that returns asset weights and summary metrics,
So that I can produce reproducible portfolio allocation POCs and verify end-to-end integration with notebooks.

**Acceptance Criteria:**

**Given** canonical `prices` or `returns` for a set of tickers
**When** `portfolio.generate(prices_df, params)` is executed
**Then** it returns a dictionary/object with `weights` (per ticker), `expected_return`, `volatility`, `sharpe` and an identifiable `run_id`
**And** the function accepts parameters (risk_target, method='equal|mean-variance', lookback_days) and is deterministic for the same inputs and params.

**FRs referenced:** FR24, FR25

### Story 6.2: Exportar resultados de modelagem em CSV/JSON

As a Data Consumer,
I want model results exported in CSV and JSON formats,
So that notebooks and downstream systems can consume allocations and metrics.

**Acceptance Criteria:**

**Given** a model run (result from `portfolio.generate`)
**When** the user runs `pipeline.model --out results/portfolio-<run_id>.csv --format csv`
**Then** a CSV with headers (`ticker,weight,expected_return,volatility,sharpe`) is written and a companion JSON metadata file with `run_id`, `params`, `created_at` and `checksum` is produced.

**FRs referenced:** FR25

### Story 6.3: Unit tests and validation for modeling functions

As a QA/Developer,
I want unit tests that validate `portfolio.generate` behavior and edge cases,
So that changes to modeling code do not break expected outputs.

**Acceptance Criteria:**

**Given** deterministic fixture data in `tests/fixtures/modeling/`
**When** `pytest tests/modeling/test_portfolio.py` runs
**Then** it validates weight normalization (sum to 1), behavior for zero-volatility assets, and that deterministic inputs produce expected weights/metrics within tolerance.

**FRs referenced:** FR24

### Story 6.4: Notebook de exemplo de modelagem (parametrizável)

As a Researcher,
I want a notebook `notebooks/modeling_example.ipynb` that demonstrates model runs and visualizes allocations,
So that stakeholders can explore sensitivity and reproduce experiments.

**Acceptance Criteria:**

**Given** sample data in `tests/fixtures/modeling/`
**When** the user runs the notebook via `papermill` or opens it interactively
**Then** it runs end-to-end, produces allocation tables, and creates basic charts (weights bar, cumulative returns) and writes the CSV/JSON outputs to `outputs/`.

**FRs referenced:** FR24, FR25

### Story 6.5: Performance and smoke metrics for model runs

As an Operator/Developer,
I want basic metrics for model runs (elapsed time, memory, rows processed),
So that we can set expectations for CI smoke tests and local runs.

**Acceptance Criteria:**

**Given** a model run on fixture data
**When** the run completes
**Then** the run emits a small JSON summary with `run_id`, `elapsed_sec`, `rows_used`, and `peak_memory_mb` and the CLI returns `--format json` support for model commands.

**FRs referenced:** FR24

### Story 6.6: Documentação e exemplos de uso para modelagem

As a Tech Writer/Developer,
I want a short `docs/modeling.md` with usage examples, expected inputs and outputs, and recommended parameter presets,
So that contributors can run the model and understand typical results.

**Acceptance Criteria:**

**Given** the repository
**When** a user opens `docs/modeling.md`
**Then** they find copy-paste commands for `poetry run main --model --tickers PETR4.SA,VALE3.SA --method mean-variance`, expected output examples, and troubleshooting notes about data quality and lookback choices.

**FRs referenced:** FR24, FR25


### Epic 7 — Testes, CI & Migrações
Objetivo: Garantir qualidade com testes unitários e integrados (mockados), scripts de migrations/versionamento e CI que valida o fluxo crítico. Owner de validação contínua (execução e hardening) — a posse inicial do pipeline (artefatos, README quickstart) está consolidada em Epic 0.
**FRs covered:** FR34, FR41, FR43

### Story 7.1: Escolher e integrar ferramenta de migrações (ou script simples)

As a Dev/Ops,
I want a migrations mechanism (Alembic or lightweight scripts) integrated into the repo,
So that schema changes are versioned, traceable and reversible.

**Acceptance Criteria:**

**Given** the repository
**When** a schema change is required
**Then** a migration file can be created (`migrations/versions/<id>_desc.py`) and the project exposes commands: `migrations status`, `migrations apply`, `migrations rollback --to <id>`
**And** migrations are recorded in a `schema_version` table in the DB after successful apply.

**FRs referenced:** FR34, FR41

**Applied recommendations (acceptance criteria additions):**

- **And** the chosen migrations tool provides a CLI workflow and can be executed in CI; provide a lightweight `migrations/__init__.py` and example `migrations/versions/` skeleton for contributors.
- **And** include a short `docs/migrations.md` entry with the minimal commands and guidance for creating a migration file and adding it to the repo.

### Story 7.2: Migrations safe-run & preflight checks

As a Developer/Operator,
I want preflight checks and a safe-run mode for migrations,
So that destructive migrations are guarded and backups are produced automatically.

**Acceptance Criteria:**

**Given** a pending migration
**When** `migrations apply --dry-run` or `migrations preflight` is executed
**Then** the tool reports affected tables, row counts (estimate), and potential breaking changes
**And** `migrations apply` creates an automatic backup to `backups/` before applying and verifies the backup via checksum.

**FRs referenced:** FR41

**Applied recommendations (acceptance criteria additions):**

- **And** the preflight command outputs an actionable summary (affected tables, estimated affected row counts, potential breaking changes) and requires a `--confirm` flag to proceed in non-interactive CI contexts.
- **And** `migrations apply` automatically takes an atomic backup to `backups/` (write-to-temp + rename) and creates a `.checksum` companion file before applying destructive changes.

### Story 7.3: CI gates for migrations and schema compatibility

As a CI Engineer,
I want CI to validate new migrations in an isolated environment,
So that PRs cannot merge breaking schema changes without verification.

**Acceptance Criteria:**

**Given** a PR that adds/changes migrations
**When** CI runs
**Then** it runs `migrations status`, applies migrations to a temporary DB, runs the test suite (unit + contract tests), and rolls back/tears down the temp DB
**And** CI fails the PR on migration apply error, test failures, or schema drift detected by `migrations status`.

**FRs referenced:** FR34, FR41, FR43

**Applied recommendations (acceptance criteria additions):**

- **And** the CI pipeline provides a job that applies migrations to a temporary DB, runs the full test matrix (unit, adapter contract, smoke), and tears down the temp DB; expected artifacts and logs are uploaded on failure for diagnosis.
- **And** CI defines a clearly documented failure mode for migrations (apply error, test failure, or schema drift) and a maintainer checklist to follow when CI blocks merge.

### Story 7.4: Test suite orchestration and integration smoke tests

As a QA/Dev,
I want a CI job that orchestrates unit, adapter contract and integration smoke tests (mocked),
So that the core ingest→snapshot→checksum flow is validated on each PR.

**Acceptance Criteria:**

**Given** a change to source code or adapters
**When** CI runs
**Then** it executes: linters, unit tests, adapters contract tests (using `--use-fixture`), quickstart smoke (using `--no-network`) and snapshot checksum validation; the job publishes artifacts for failed runs.

**FRs referenced:** FR26, FR37, FR43

**Applied recommendations (acceptance criteria additions):**

- **And** the CI job sequence is documented in `docs/ci/migrations.md` and exposes a single orchestrator script (e.g., `.github/workflows/ci.yml` step or `scripts/ci_orchestrator.sh`) to run: lint → unit → contract (adapters with fixtures) → quickstart smoke (`--no-network`) → checksum validation.
- **And** failed artifacts (CSV, checksum, logs) are published to CI job artifacts for debugging.

### Story 7.5: Migration rollback tests and restore verification

As an Operator,
I want automated tests that verify migration rollback and restore paths,
So that we can validate recovery procedures.

**Acceptance Criteria:**

**Given** a migration set
**When** the rollback test runs in CI or locally
**Then** it applies migrations, inserts sample data (fixtures), rolls back to a previous version, and verifies that expected constraints and row counts are consistent with the target version.

**FRs referenced:** FR41

**Applied recommendations (acceptance criteria additions):**

- **And** rollback tests are automated in CI: apply migrations, insert fixture data, run rollback, and then run assertions that verify schema and row counts for restored version; test must be runnable locally with `pytest tests/migrations/test_rollback.py`.
- **And** the test emits a short JSON summary of the verification results (`passed`, `failed_checks`, `time_ms`) for CI consumption.

### Story 7.6: Continuous validation job (nightly or scheduled)

As an Owner/CI Engineer,
I want a scheduled job that runs a full validation (ingest from fixtures, snapshot generation, checksum validation, basic metrics),
So that regressions are detected outside PR context.

**Acceptance Criteria:**

**Given** the scheduled runner (e.g., GitHub Actions workflow or cron)
**When** the job runs
**Then** it runs quickstart with fixtures, generates snapshots, computes checksums, runs integrity checks and reports failures (and publishes artifacts) to a chosen channel (logs/artifacts/webhook).

**FRs referenced:** FR26, FR37, FR40

**Applied recommendations (acceptance criteria additions):**

- **And** the scheduled job publishes a short report (JSON) including `job_id`, `status`, `elapsed_sec`, `snapshots_generated`, and `checksums_verified`; failures produce artifacts for investigation and optionally send a notification to a configured webhook.
- **And** the schedule and retention policy for artifacts are documented in `docs/ci/migrations.md`.

### Story 7.7: Migration & CI documentation and runbook updates

As a Tech Writer/Dev,
I want migration and CI runbooks updated with commands and rollback procedures,
So that contributors and operators can follow safe steps to change schema and validate PRs.

**Acceptance Criteria:**

**Given** the repository
**When** a user opens `docs/migrations.md` or `docs/ci/migrations.md`
**Then** they find step-by-step commands for creating migrations, preflight checks, applying/rolling back, and interpreting CI failures with example outputs.

**FRs referenced:** FR34, FR41, FR43

**Applied recommendations (acceptance criteria additions):**

- **And** the documentation includes a step-by-step recovery checklist for operators, sample commands for local reproduction of CI failures, and an owner contact list for escalation.
- **And** the runbook contains example outputs for success and failure cases and a quick triage flow (check ingest_logs → check backups → restore to temp DB → file an incident/PR).



**Nota:** Epic 7 referencia e valida os artefatos entregues por Epic 0 (CI/README) e por Epic 1/2 (fluxo ingest/snapshot) como parte da validação contínua.

### Epic 8 — Segurança Operacional
Objetivo: Aplicar políticas operacionais mínimas: permissões do DB, gestão de segredos, `.env.example` e recomendações de segurança local.
**FRs covered:** FR32, FR33

### Story 8.1: Garantir permissões mínimas para artefatos sensíveis

As an Operator,
I want the system to enforce owner-only permissions for `dados/data.db` and backups,
So that sensitive data at rest is not world-readable by default.

**Acceptance Criteria:**

**Given** the DB or backup file is created
**When** the creation completes
**Then** the file receives owner-only permissions (`chmod 600`) by default and a verification command `main security verify-perms` returns pass
**And** the runbook documents the verification command and remediation steps.

**FRs referenced:** FR32

### Story 8.2: `.env.example` e gerenciamento seguro de segredos locais

As a Developer,
I want a clear `.env.example` and guidance for secret handling,
So that contributors do not commit secrets and can run locally using `python-dotenv` safely.

**Acceptance Criteria:**

**Given** the repository
**When** a contributor copies `.env.example` to `.env` and populates values
**Then** the README documents required vs optional vars and warns against committing `.env`
**And** a pre-commit hook is suggested/installed to detect secrets (e.g., `detect-secrets`) and fail commits when secrets are present.

**FRs referenced:** FR33

### Story 8.3: Scan de dependências e Snyk/CVE checks no CI

As a Security Engineer,
I want CI to run dependency scanning (Snyk or equivalent) and fail on high severity findings,
So that known vulnerabilities are flagged early.

**Acceptance Criteria:**

**Given** a PR that modifies dependencies
**When** CI runs
**Then** a dependency scan step runs (Snyk/code scanning) and the job fails or warns depending on policy; the report is attached to the PR as an artifact
**And** any new high severity CVEs block merge until triaged.

**FRs referenced:** (security best practices)

### Story 8.4: Secret scanning & pre-commit enforcement

As a Maintainer,
I want secret scanning in pre-commit and CI (detect-secrets + CI verification),
So that no secrets are committed to the repo and any leak is detected early.

**Acceptance Criteria:**

**Given** a commit or PR
**When** hooks run locally or CI runs pre-merge checks
**Then** secret scanner identifies potential secrets and fails the commit/CI step (with guidance to rotate secrets if present)
**And** the repo contains `.github/ISSUE_TEMPLATE` or runbook steps for secret rotation and incident reporting.

**FRs referenced:** FR33

### Story 8.5: Minimal network + container security guidance

As an Operator/Dev,
I want minimal guidance for running the POC and containers securely,
So that local or demo deployments do not expose secrets or open unnecessary ports.

**Acceptance Criteria:**

**Given** a developer running the Streamlit POC or container locally
**When** they follow the README guidance
**Then** the documentation includes steps to run containers with least-privilege (non-root user), bind localhost-only, and set environment variables via `.env` or secret manager
**And** a short checklist is present in `docs/operations/runbook.md` about exposed ports, recommended Docker user, and network restrictions.

**FRs referenced:** FR23, FR33

### Story 8.6: Incident response runbook and secret-rotation checklist

As an Operator/Security Owner,
I want a concise incident response runbook for detected secret leaks or DB compromise,
So that on-call engineers can follow a reproducible checklist to rotate credentials, restore backups and notify stakeholders.

**Acceptance Criteria:**

**Given** a detected secret leak or compromise
**When** the incident runbook is followed
**Then** the runbook lists step-by-step actions: rotate affected keys, revoke provider keys, restore DB from verified backup if needed, update affected artifacts, and file an incident report
**And** the runbook includes sample commands and expected outputs and contact/ownership information.

**FRs referenced:** FR33, FR40


### NFR Coverage Map

NFR-P1: Epic 3 - Quickstart performance (quickstart end-to-end)
NFR-P2: Epic 4 - Healthcheck/metrics responsiveness
NFR-P3: Epic 2 - Snapshot generation performance
NFR-R1: Epic 1 - Retries/backoff and ingest reliability
NFR-R2: Epic 4 - Backup/restore and operational resilience
NFR-O1: Epic 4 - Logs and observability
NFR-O2: Epic 4 - Metrics exposure via CLI
NFR-S1: Epic 1 / Epic 4 - Concurrency handling (operational controls in Epic 4, runtime guarantees in Epic 1)
NFR-S2: Epic 5 / Epic 1 - Design for batch/multi-ticker extensibility (architectural note)
NFR-Sec1: Epic 8 - DB permissions and operational security
NFR-M1: Epic 7 - Migrations/versioning and rollback support
NFR-M2: Epic 7 - CI validation gates for CSV/checksum and integration tests
NFR-INT1: Epic 5 - Adapter interface stability, retries and rate-limit logging

## Dependencies / Prerequisites

- Epic 0 (Preparação do Ambiente) → deve ser entregue primeiro para fornecer `pyproject.toml`, `README` quickstart, `pre-commit` e CI skeleton. (Precede: Epic 1, Epic 3, Epic 7)
- Epic 1 (Ingestão e Persistência) → contém adaptadores críticos; necessário para gerar dados canônicos. (Precede: Epic 2, Epic 3, Epic 4, Epic 6)
- Epic 5 (Adaptadores & Normalização - expansão) → pode ser executado paralelamente, mas trabalhos de expansão de provedores dependem de infra da Epic 1.
- Epic 2 (Snapshots & Exportação) → depende de Epic 1 para dados persistidos e deve ser implementada antes de validações finais de CI em Epic 7.
- Epic 3 (Quickstart CLI & Notebooks) → requer Epic 0 (setup) e Epic 1 (ingest) para funcionar end-to-end.
- Epic 4 (Operações & Observabilidade) → depende de Epic 1 e Epic 2 para fornecer logs, métricas e backup/restore operacional.
- Epic 6 (Modelagem de Portfólio) → depende de Epic 1 para dados e pode be developed after core ingestion is stable.
- Epic 7 (Testes, CI & Migrações) → depends on Epic 0 for CI artifacts and on Epic 1/2 for validating functional flows; run continuously as validation gateway.
- Epic 8 (Segurança Operacional) → can be implemented incrementally; initial deliverables (DB permissions, `.env.example`) should be applied early (after Epic 0) and hardened over time.

Observação: Recomenda-se sequência mínima de entrega: Epic 0 → Epic 1 → Epic 2 → Epic 3 → Epic 4 → Epic 6 (parallelizable) → Epic 5 (expansão) → Epic 7 (validação contínua) → Epic 8 (hardening contínuo).

<!-- Repeat for each epic in epics_list (N = 1, 2, 3...) -->

## Epic {{N}}: {{epic_title_N}}

{{epic_goal_N}}

<!-- Repeat for each story (M = 1, 2, 3...) within epic N -->

### Story {{N}}.{{M}}: {{story_title_N_M}}

As a {{user_type}},
I want {{capability}},
So that {{value_benefit}}.

**Acceptance Criteria:**

**Given** {{precondition}}
**When** {{action}}
**Then** {{expected_outcome}}
**And** {{additional_criteria}}

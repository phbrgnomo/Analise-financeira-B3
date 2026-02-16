---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - docs/planning-artifacts/prd.md
  - docs/planning-artifacts/product-brief-Analise-financeira-B3-2026-02-15.md
  - docs/planning-artifacts/research/technical-techstack-implementacao-b3-research-2026-02-15.md
  - docs/planning-artifacts/prd-validation-2026-02-15.md
workflowType: 'architecture'
project_name: Analise-financeira-B3
user_name: Phbr
date: 2026-02-16
lastStep: 8
status: 'complete'
completedAt: 2026-02-16
---

# Architecture Decision Document

## Project Context Analysis

### Requirements Overview

**Functional Requirements (resumo):**
- Ingestão idempotente por ticker com adaptadores para múltiplos provedores; flags operacionais (`--force-refresh`, `--use-cache`).
- Persistência canônica em SQLite; as tabelas serão definidas com base nas respostas dos provedores de dados (colunas e campos serão alinhados ao formato retornado pelos adaptadores).
- Geração de snapshot CSV com checksum SHA256 e metadados armazenados.
- APIs/contratos para leitura/gravação (`db.read_prices`, `db.write_prices`), pipeline de ingest (`pipeline.ingest`) e geração de portfólios (`portfolio.generate`).
- Notebooks reprodutíveis e POC Streamlit que leem do SQLite.
- Operações: backups, health checks, logs estruturados e rotinas de monitoramento via CLI.

**Non-Functional Requirements (resumo):**
- Resiliência: retries/backoff, fallback para raw CSV, logs com erro contextual.
- Observabilidade: logs JSON e métricas básicas (`job_latency`, `rows_fetched`, `error_rate`).
- Performance: quickstart reproduzível em ambiente dev; geração de snapshots eficiente para séries históricas.
- Segurança operacional: proteger `dados/data.db` (permissões), não commitar segredos; `.env` para credenciais.
- Escalabilidade/Concorrência: projeto destinado a uso local por um único usuário por vez — exigência explícita de estratégias de concorrência (fila por ticker, locks ou mover para RDBMS) é desnecessária neste escopo.

### Technical Constraints & Dependencies
- Dependência de provedores externos (yfinance, AlphaVantage, Twelve Data) com limites e formatos distintos.
- Persistência local em SQLite (trade-off: simplicidade vs concorrência) — estrutura das tabelas será definida a partir do formato retornado pelos provedores e pelos adaptadores implementados.
- Recomendado: SQLAlchemy para abstração DB, `pandas` para ETL, `poetry` para gerenciamento de dependências.

### Scale & Complexity

- **Complexity Assessment:** medium — o projeto combina processamento de séries temporais, integração com múltiplos provedores e necessidade de auditabilidade, mas é restrito a execução local e um único usuário por vez.
- **Primary technical domain:** backend / data-processing (ETL, persistência local, CLI) com componente de visualização leve (Streamlit) e notebooks para análise.
- **Scale indicators:** volume de dados por ticker (anos de séries diárias), necessidade de retenção de snapshots e número de provedores integrados.
- **Architectural components (sugeridos):**
  1. Ingest / Adapters
  2. Adapter -> Canonical Mapper
  3. ETL / Processing (retornos, cleaning)
  4. DB Layer + Migrations (SQLite)
  5. Snapshot Manager / Exporter
  6. CLI / Orchestration + Runbook
  7. Notebooks / Streamlit POC

- **Complexity drivers:** multi-provider normalization, auditability (raw responses + checksums), and testability (mocking providers in CI).

**Observability / Concurrency (pragmatic):**

- Projeto é destinado a uso local single‑user. Implementações sofisticadas de telemetria distribuída, locks/enqueue e filas são overkill para o MVP. Documente a rota de migração — como migrar para Redis/RabbitMQ e implementar locks por ticker — caso seja necessário escalar no futuro. Marcar como **Phase 3** para avaliação quando houver necessidade de múltiplos usuários/concorrência.

**Frameworks & Validation choices (pragmatic):**

- Streamlit é aceitável como POC — não introduza dashboards complexos de produção nesta fase. 
- Para validação de DataFrames use `pandera`. `pydantic` permanece recomendado para configurações/DTOs, mas não é indicado para validação de DataFrames (não substituir `pandera`).


**Modeling & Research features (phasing):**

- Recursos avançados de modelagem (ex.: Black‑Litterman completo, fronteira eficiente com otimizações extensas) são research‑heavy e não necessários para o MVP. Esses itens devem ser classificados como **Phase 4 (research/advanced)** e não bloqueadores do desenvolvimento inicial.
- Para o MVP, priorize funções estatísticas básicas e úteis: média, variância, volatilidade anualizada, correlação, covariância e uma implementação básica de Markowitz para POC. Se/Quando decidirem evoluir, considere `pyportfolioopt` como opção prática para otimizações mais avançadas.

**Testing strategy (CI):**

- Na pipeline CI inicial, **mockar provedores** e executar um quickstart integrado (mocked) que valide ingest→persistência→snapshot→checksum. Testes que fazem chamadas reais a provedores externos devem ser movidos para **Phase 3** (integração opcional/manual) para evitar instabilidade e rate‑limit flakiness em CI.

### Cross-Cutting Concerns Identified
- Data integrity and provenance (store `source`, `fetched_at`, `raw_response`).
- Idempotency and upsert semantics.
- Observability and reproducibility (checksums, run metadata).
- Testing and CI coverage for end‑to‑end flows (mock provedores).
- Operational runbooks: backup/restore, health checks, error handling.

### Adapter Normalization & Schema Strategy

- Persistência canônica: o projeto usará SQLite localmente; as tabelas e colunas serão definidas pelos adaptadores com base nos campos retornados pelos provedores de dados. Cada ingest deverá armazenar também o `raw_response`, `source` e `fetched_at` para auditoria e reprocessamento.
- Recomenda-se implementar uma camada `Adapter -> Canonical Mapper` que: 1) recebe o `DataFrame` bruto do adaptador, 2) normaliza tipos/colunas, 3) preenche metadados mínimos (`source`, `fetched_at`, `raw_checksum`) e 4) emite o schema canônico usado pelo `db` layer.
- Documentar mappings por provedor em `docs/planning-artifacts/adapter-mappings.md` (ex.: yfinance → canonical mapping). Isso facilita adicionar novos provedores sem alterar a camada de persistência.

### Migration Path (leve)

- Observação: embora este projeto seja para uso local por um único usuário, incluir no `docs/` uma rota de migração simples é útil caso seja necessário suportar múltiplos usuários no futuro. A rota deve descrever sinais de escala (ex.: concorrência de writers, latência) e passos recomendados (mover para PostgreSQL, adicionar fila por job, introduzir worker pool).

**Migrations (pragmatic approach for MVP):**

- Para a fase inicial (MVP) evite introduzir `alembic`/migrações completas sobre SQLite — isso tende a acrescentar complexidade operacional sem necessidade imediata. Em vez disso, comece com pequenos scripts de versionamento/binários SQL (ex.: `migrations/simple/0001_init.sql`, `migrations/apply.sh`) que aplicam mudanças incrementais e registram a versão atual em uma tabela `schema_version`.
- Marque a avaliação de necessidade de `alembic` e migrações avançadas como **Phase 3: Enable when needed** — só adotar `alembic` se o projeto passar para multi‑usuário ou exigir migrações complexas que justifiquem a sobrecarga.

### Developer Next Steps (sugestão imediata)

- Criar esqueleto de adaptador em `src/dados_b3.py` com interface `Adapter.fetch(ticker) -> pd.DataFrame(raw)` e `Adapter.normalize(df) -> pd.DataFrame(canonical)`.
- Implementar `src/db.py` com `write_prices(df, ticker)` garantindo upsert por `(ticker, date)`.
- Adicionar testes: `tests/test_ingest.py` (mock adapters) e `tests/test_db_upsert.py` (fixture SQLite temporário) para validar idempotência e integridade dos snapshots.
- Adicionar `docs/planning-artifacts/adapter-mappings.md` com exemplos de mapeamento por provedor.

## Starter Template Evaluation (Step 03)

### Party Mode Consolidated Recommendation

- **Starter escolhido:** Custom Lightweight Python starter (Poetry + Typer + pandas + SQLAlchemy + Streamlit + pytest + black/ruff + python-dotenv).
- **Rationale:** leve, alinhado ao PRD, testável, facilita criação de adaptadores e não impõe complexidade desnecessária ao escopo local single-user.

### Init / Quickstart (exemplo)

```bash
# criar projeto e pyproject com poetry
poetry init -n

# adicionar dependências de runtime
poetry add pandas sqlalchemy yfinance pandas-datareader python-dotenv typer streamlit

# adicionar dependências de desenvolvimento
poetry add --dev pytest black ruff pre-commit

# criar layout inicial
mkdir -p src tests notebooks docs dados snapshots
```

### Decisões arquiteturais que o starter estabelece

- Language & Runtime: Python + Poetry (ambiente isolado e packaging).
- CLI: `Typer` para comandos (`pipeline.ingest`, `db.*`, `snapshots`).
- DB: SQLite via SQLAlchemy (camada de abstração); documentar migração/versão.
- Testing: `pytest` com fixtures para SQLite temporário; testes de contrato para adaptadores.
- Formatting/Linting: `black` + `ruff` + `pre-commit`.
- Dev DX: `poetry run` para comandos e `python -m src.main` como fallback.

### Party Mode Action Items (para implementação imediata)

- Implementar `src/dados_b3.py` com interface `Adapter.fetch(ticker) -> pd.DataFrame(raw)` e `Adapter.normalize(df) -> pd.DataFrame(canonical)`.
- Implementar `src/db.py` com `write_prices(df, ticker)` garantindo upsert por `(ticker, date)`.
- Criar testes iniciais: `tests/test_ingest.py` (mock adapters) e `tests/test_db_upsert.py` (fixture SQLite temporário).
- Incluir `pre-commit` com hooks para `black` e `ruff`.
- Documentar no `architecture.md` e em `docs/planning-artifacts/adapter-mappings.md` os mapeamentos e checklist por provedor.

### Notas

- Confirmar versões dos pacotes via pesquisa web antes de fixar no `pyproject.toml`.
- Incluir no `docs/` uma rota de migração leve para PostgreSQL caso o projeto evolua para multi-usuário.

## Core Architectural Decisions — Data Architecture (Step 04)

- Banco: SQLite local (single‑user); migrar para PostgreSQL se necessário.
- Modelo: Adapter → Canonical Mapper; adaptadores entregam raw + DataFrame; mapper normaliza e adiciona source, fetched_at, raw_checksum.
- Persistência: tabelas canônicas (prices, ingest_logs, snapshots); upsert por (ticker, date) (INSERT OR REPLACE / ON CONFLICT).
- Provenance: salvar raw_response em raw/<provider>/ e registrar checksum SHA256.
- Validação: pandera para DataFrames; pydantic para configs/DTOs.
- Migrations: scripts simples para MVP; avaliar alembic em fase de escala.
- Observabilidade: logs JSON estruturados + metadados de snapshot (checksum, created_at).

## Implementation Patterns — Party Mode Consolidated (Step 05)

Resumo das convenções e padrões acordados pela revisão colaborativa:

- Convenções de nomes
  - Tabelas: plural, snake_case (ex.: `prices`, `ingest_logs`, `snapshots`).
  - Colunas: snake_case (`ticker`, `fetched_at`, `raw_checksum`).
  - Código Python: snake_case para funções/variáveis; PascalCase para classes.
  - Arquivos: snake_case.py (`dados_b3.py`, `db.py`).
  - CLI: comandos kebab-like (`poetry run main ingest --ticker PETR4.SA`).

- Estrutura do repositório
  - `src/`
    - `src/adapters/` (adaptadores por provider)
    - `src/ingest/`
    - `src/db/` (camada SQLAlchemy, migrations)
    - `src/etl/` (transformações / canonical mapper)
    - `src/cli.py` (Typer entrypoints)
    - `src/apps/streamlit_poc.py`
  - `tests/` (todos `test_*.py`, `conftest.py` com fixtures)
  - `docs/`, `notebooks/`, `dados/`, `snapshots/`, `raw/`

- Modelagem & ingest
  - Adapter → Canonical Mapper padrão; adaptadores normalizam e preenchem `source`, `fetched_at`, `raw_checksum`.
  - Persistência: SQLite, upsert por `(ticker, date)` via helper SQLAlchemy (`INSERT OR REPLACE` / `ON CONFLICT`).
  - Salvar raw responses em `raw/<provider>/` com SHA256 para auditoria e reprocessamento.

- Validação & testes
  - Validação leve no adaptador; `pandera` recomendado para validação de DataFrames em testes; `pydantic` para configs/DTOs.
  - Tests obrigatórios para novos adaptadores (contract tests) + integração mockada para `pipeline.ingest` → snapshot + checksum.
  - Fixtures de SQLite temporário em `tests/conftest.py`.

- Migrations, CI e qualidade
  - `alembic` para migrações/versão do schema (documentar limitações em SQLite).
  - `pre-commit` com `black`, `ruff`.
  - CI: `poetry install`, `pytest`, `ruff/black` — falhar o merge em caso de erro.

- Observabilidade e formatos
  - Logging estruturado JSON com campos: `job_id`, `ticker`, `source`, `started_at`, `finished_at`, `rows_fetched`, `status`, `error`.
  - Erros padronizados: `{ "error": { "code": "ERROR_CODE", "message": "mensagem legível" } }`.
  - Datas: ISO 8601 UTC; CSV snapshots com cabeçalho snake_case + metadados (checksum, created_at).

- Enforcement & processo
  - Todos os agentes devem seguir as convenções; desvios documentados em `docs/` + PR justificando a alteração.
  - Violação de padrão: registrar no PR checklist e bloquear merge até correção.
  - Incluir templates de PR/checklist e exemplos de mapeamento em `docs/planning-artifacts/adapter-mappings.md`.

## Project Structure & Boundaries (Step 06)

### Complete Project Directory Structure

```
analise-financeira-b3/
├── README.md
├── pyproject.toml
├── poetry.lock
├── .env.example
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   ├── planning-artifacts/
│   │   ├── architecture.md
│   │   └── adapter-mappings.md
│   |── playbooks/
|   └── implantacao/
├── dados/                # persistência e artefatos de dados (mounted volume)
├── raw/                  # raw responses salvos por provider
├── snapshots/            # snapshot CSVs com checksum
├── notebooks/
├── src/
│   ├── __init__.py
│   ├── main.py           # entrypoint fallback: python -m src.main
│   ├── cli.py            # Typer entrypoints
│   ├── adapters/         # providers: yfinance, alphavantage, twelvedata
│   │   ├── __init__.py
│   │   └── yfinance_adapter.py
│   ├── ingest/           # orchestration and job logic
│   │   └── pipeline.py
│   ├── etl/              # canonical mapper and transforms
│   │   └── mapper.py
│   ├── db/               # SQLAlchemy models, helpers, migrations config
│   │   ├── __init__.py
│   │   └── db.py
│   ├── apps/
│   │   └── streamlit_poc.py
│   └── utils/
│       └── checksums.py
├── migrations/           # alembic files or migration scripts
└── tests/
  ├── test_ingest.py
  ├── test_db_upsert.py
  └── conftest.py
```

### Mapping de Requisitos → Localizações

- Ingestão idempotente / adaptadores → `src/adapters/`, `src/ingest/pipeline.py`  
- Persistência (prices/returns/ingest_logs/snapshots/metadata) → `src/db/db.py`, `migrations/`  
- Canonical mapping / ETL → `src/etl/mapper.py`  
- Snapshot export + checksum → `src/etl/mapper.py` / `src/utils/checksums.py` / `snapshots/`  
- Notebooks e POC Streamlit → `notebooks/`, `src/apps/streamlit_poc.py`  
- Tests / fixtures → `tests/` (unit + integration mockado)  
- Docs / adapter mappings → `docs/planning-artifacts/adapter-mappings.md`

### Integration & Boundaries

- API/CLI boundary: `src/cli.py` exposes commands; internal modules must not read env directly (use config loader).  
- DB boundary: `src/db/db.py` is única interface para leitura/gravação; adaptadores/etl chamam helpers expostos por essa camada.  
- Raw storage boundary: adaptadores escrevem em `raw/<provider>/` e registram metadados em `ingest_logs`/`metadata`.

### File & Naming Rules (enforced)

- Arquivos Python: snake_case.py; classes PascalCase.  
- Tables & columns: snake_case, tables plural (`prices`, `returns`).  
- Tests: `test_*.py` em `tests/` e fixtures em `conftest.py`.

## Architecture Validation Results (Step 07)

### Coherence Validation ✅

- **Decision Compatibility:** todas as escolhas (Python + Poetry, Typer CLI, pandas, SQLAlchemy, SQLite local, adapter→mapper, pandera/pydantic para as responsabilidades indicadas) são compatíveis e coerentes entre si. Não há conflitos arquiteturais detectados.
- **Pattern Consistency:** as regras de naming, estrutura e processos (logging, raw storage, upsert) suportam as decisões de arquitetura; convenções aplicadas reduzem risco de divergência entre agentes.
- **Structure Alignment:** árvore de projeto e boundaries suportam requisitos principais (ingest, ETL, persistência, snapshots, notebooks/POC).

### Requirements Coverage Validation ✅

- **Functional Requirements:** ingestão idempotente, persistência, snapshots com checksum, CLI quickstart, notebooks e POC Streamlit estão mapeados para módulos e locais no repositório (adapters, ingest, etl, db, apps). FRs críticos (upsert, snapshot checksum, quickstart) têm local e fluxo claros.
- **Non-Functional Requirements:** observabilidade (logs JSON), testes (pytest + fixtures), validação leve (adaptadores + pandera recomendado) e segurança operacional (permissões do arquivo `dados/data.db` documentadas) foram contempladas. Migrações e limitações do SQLite estão reconhecidas e documentadas.

### Implementation Readiness Validation ✅

- **Decision Completeness:** decisões críticas estão documentadas com rationale e exemplos de inicialização. Versões explícitas de pacotes ainda precisam ser confirmadas antes de fixar o `pyproject.toml`.
- **Structure Completeness:** árvore de projeto e mapeamento de requisitos estão completos e específicos; pontos de integração e boundaries estão definidos.
- **Pattern Completeness:** naming, formatos, validação e processos de observabilidade foram cobertos; enforcement process (PR checklist, docs) definido.

### Gap Analysis

- **Crítico (ação recomendada antes da implementação ampla):** fixar ou verificar versões estáveis dos pacotes no `pyproject.toml` e criar o arquivo `pyproject.toml` mínimo (starter). Criar configuração mínima do `alembic` (migrations) e roteiro de migração inicial.
- **Importante:** adicionar `pre-commit` config, `pytest` conftest fixtures exemplo, e CI workflow `ci.yml` que roda `poetry install`, `pytest`, `ruff`/`black` e checks de geração de snapshot mockada.
- **Nice-to-have:** exemplos de dados de teste (small sample CSV), PR/issue templates, e documentação de monitoramento local (ex.: healthcheck CLI).

### Validation Issues Addressed

- Documentei a limitação de concorrência do SQLite e optei por NÃO impor mecanismo de fila/locks agora (escopo single-user), adicionando rota de migração em `docs/` caso evolua para multi‑usuário.
- Confirmei a estratégia de validação (pandera para DataFrames, pydantic para configs/DTOs) e registrei recomendações de testes.

### Architecture Readiness Assessment

- **Overall Status:** READY FOR IMPLEMENTATION
- **Confidence Level:** high — a arquitetura cobre requisitos funcionais e não-funcionais essenciais; pequenas ações práticas (fixar versões, criar CI skeleton, adicionar fixtures) deixarão o projeto imediatamente implementável.

**Key Strengths:**
- Simplicidade e alinhamento com escopo local (SQLite).  
- Clareza na separação Adapter→Mapper→DB, facilitando novos provedores.  
- Padrões e enforcement definidos (naming, logging, tests).

**Areas para melhoria posterior (não-blocking):**
- Fixar versões de dependências no `pyproject.toml`.  
- adicionar exemplos de fixtures e dados de amostra para testes de integração.  
- criar templates de PR/checklist e CI job de integração mockada.

### Implementation Handoff

**AI Agent Guidelines:**
- Implementar exatamente as convenções e patterns deste documento.  
- Cobrir novos adaptadores com testes de contrato e incluir mapping em `docs/planning-artifacts/adapter-mappings.md`.  
- Registrar quaisquer desvios no PR e anexar justificativa.

**First Implementation Priority (primeiros passos):**
1. Inicializar projeto (`poetry init -n`) e adicionar dependências iniciais (veja exemplo do Step 03).  
2. Criar esqueleto: `src/adapters/`, `src/ingest/pipeline.py`, `src/etl/mapper.py`, `src/db/db.py`, `tests/conftest.py`.  
3. Adicionar `pre-commit` e CI `ci.yml` básico com `pytest` e lint.

**Comando inicial sugerido:**
```bash
poetry init -n
poetry add pandas sqlalchemy yfinance pandas-datareader python-dotenv typer streamlit
poetry add --dev pytest black ruff pre-commit alembic
mkdir -p src/adapters src/ingest src/etl src/db src/apps tests dados raw snapshots notebooks
```

**Decisões escolhidas pelo usuário:**
- **Banco:** SQLite (local)  
- **Modelagem:** Adapter → Canonical Mapper  
- **Upsert / Idempotência:** `INSERT OR REPLACE` / `ON CONFLICT` (implementado via helper SQLAlchemy)  
- **Validação:** Validação leve no adaptador + testes de contrato (opção leve)  
- **Migrações:** `alembic` para versionamento de esquema  
- **Caching / Raw storage:** salvar `raw_response` em `raw/<provider>/` e usar TTL cache local (reduz chamadas)

**Ações operacionais aplicadas:**
- Adaptadores devem sempre salvar o `raw_response`, calcular `raw_checksum` (SHA256) e registrar `source` + `fetched_at` nos metadados.
- Implementar cache local com TTL no adaptador e fallback para reprocessamento a partir do `raw` salvo.
- Garantir upsert por `(ticker, date)` para idempotência; expor helper em `src/db.py`.

### Nota técnica — `pandera` vs `pydantic`
- `pandera` é focado em validação de DataFrames/pandas: permite declarar schemas por coluna (tipo, nullability, ranges), validar transformações ETL e integrar diretamente em testes `pytest`. É a escolha natural quando a principal unidade de trabalho é um `pandas.DataFrame`.
- `pydantic` é excelente para validação de modelos Python, parsing de JSON/inputs e validação de registros individuais (DTOs, configurações). Não é tão conveniente para validação de DataFrames inteiros.
- Recomendação prática: usar **`pandera`** para validação de DataFrames e pipelines ETL; usar **`pydantic`** para validação de configurações, inputs de API e contratos de adaptador (objetos/records).


## Step 8 — Conclusão & Handoff (FINAL)

Parabéns — a arquitetura foi concluída colaborativamente e está pronta para implementação.

- **O que entregamos:** documento de arquitetura completo com análise de contexto, decisões arquiteturais, padrões de implementação, estrutura do projeto, mapeamento de requisitos e validação de prontidão (STEPs 1..8).
- **Status:** complete (workflow marcado como finalizado). Todas as decisões essenciais estão documentadas e validadas.

**Próximos passos recomendados (imediatos):**
- Inicializar o projeto com `poetry init -n` e adicionar dependências listadas no documento (veja seção Starter / Quickstart).
- Criar o esqueleto de código (`src/adapters`, `src/ingest`, `src/etl`, `src/db`, `tests/`, `migrations/`) e os fixtures mínimos em `tests/conftest.py`.
- Adicionar `pyproject.toml` com versões fixas após verificar as versões estáveis recomendadas.
- Criar CI mínimo em `.github/workflows/ci.yml` que rode `poetry install`, `pytest` e linters (`ruff`/`black`).

Se quiser, eu posso: criar automaticamente o `pyproject.toml` mínimo, o esqueleto `src/` e `tests/`, um `ci.yml` básico e a configuração `pre-commit` — confirme que devo prosseguir com essas alterações.

Para referência operacional e ajuda automática do workflow, consulte o helper local: `_bmad/core/tasks/help.md` com argumento `Create Architecture`.

Se houver dúvidas ou quiser que eu gere os artefatos operacionais agora, diga “Sim — gerar esqueleto” ou peça modificações específicas.

---



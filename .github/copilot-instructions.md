<!-- Project Guidelines: quick, actionable guidance for AI agents -->
# Project Guidelines

!!MANDATORY!!
- before starting any implementation, review `project-context.md`.

## Code Style
- Linting: `ruff` config is in `pyproject.toml` (line-length 88). Run `poetry run ruff check src tests`.
- Tests use `pytest` (see `tests/`). Follow existing test patterns and fixtures in `src/tests` and `tests/conftest.py`.

## Architecture
- Always reference `docs/architecture.md` for high-level design and rationale.
- Single-package Python app: core modules live in `src/` (ex.: `src/db.py`, `src/main.py`, `src/validation.py`).
- Persistence: lightweight SQLite via SQLAlchemy Core; `dados/` holds runtime DB and data snapshots (`snapshots/`, `dados/`).
- ETL and adapters live under `src/adapters/`, `src/etl/`, and `scripts/` for small helpers.
- Adapter guidelines and patterns are in `docs/modules/adapter-guidelines.md` (fetch helpers, retry logic, metadata, testing).

## Playbooks and Instructions
- Follow playbooks in `docs/playbooks/` for common tasks (ex.: `quickstart-ticker.md`, `testing-network-fixtures.md`).

## Implementation Notes
- Past implementations are documented in `docs/sprint-reports/`
- Database canonical schema is documented in `docs/schema.md`

## Build and Test
- Install developer env: `poetry install` (project uses Poetry).
- Run tests: `poetry run pytest -q`.
- Run CLI/app: `poetry run main` (entrypoint configured in `pyproject.toml`).

## Before Committing the changes
- Run `poetry run pre-commit --all-files` to apply formatting and lint fixes.
- Ensure tests pass: `poetry run pytest`.

## Project Conventions
- Data files: small example CSVs are kept in `dados/` and `snapshots/` for tests—avoid committing large raw datasets. Place additional sample files under `dados/samples` or `snapshots/` and add a corresponding checksum entry in `snapshots/checksums.json` when needed.
- DB path default: `dados/data.db`. Tests typically inject a temporary `engine` or override `db_path` via fixtures; follow patterns in `tests/conftest.py`.
- Idempotency: `src/db.py` computes a `raw_checksum` to avoid unnecessary upserts—respect this behavior when writing adapters or ETL scripts.
- CLI helpers: many scripts in `scripts/` (e.g. `validate_snapshots.py`, `init_ingest_db.py`) exist for one-off tasks; read their headers when extending.

## Integration Points
- External APIs: `yfinance` (see `pyproject.toml`)—mock network calls in unit tests using fixtures in `tests/fixtures`.
- Persistence: SQLite via SQLAlchemy (see `src/db.py`); prefer `engine` injection in tests.

## Security
- Secrets/config: use environment variables and `.env` (project uses `python-dotenv`). Do NOT commit credentials or `.env` files.
- Avoid printing secrets to logs; prefer structured logging via `src/logging_config.py`.

---

<!-- BMAD:START -->
# BMAD Method — Project Instructions

## Project Configuration

- **Project**: Analise-financeira-B3
- **User**: Phbr
- **Communication Language**: PT-BR
- **Document Output Language**: PT-BR
- **User Skill Level**: intermediate
- **Output Folder**: {project-root}/docs
- **Planning Artifacts**: {project-root}/docs/planning-artifacts
- **Implementation Artifacts**: {project-root}/docs/implementation-artifacts
- **Project Knowledge**: {project-root}/docs

## BMAD Runtime Structure

- **Agent definitions**: `_bmad/bmm/agents/` (BMM module) and `_bmad/core/agents/` (core)
- **Workflow definitions**: `_bmad/bmm/workflows/` (organized by phase)
- **Core tasks**: `_bmad/core/tasks/` (help, editorial review, indexing, sharding, adversarial review)
- **Core workflows**: `_bmad/core/workflows/` (brainstorming, party-mode, advanced-elicitation)
- **Workflow engine**: `_bmad/core/tasks/workflow.xml` (executes YAML-based workflows)
- **Module configuration**: `_bmad/bmm/config.yaml`
- **Core configuration**: `_bmad/core/config.yaml`
- **Agent manifest**: `_bmad/_config/agent-manifest.csv`
- **Workflow manifest**: `_bmad/_config/workflow-manifest.csv`
- **Help manifest**: `_bmad/_config/bmad-help.csv`
- **Agent memory**: `_bmad/_memory/`

## Key Conventions

- Always load `_bmad/bmm/config.yaml` before any agent activation or workflow execution
- Store all config fields as session variables: `{user_name}`, `{communication_language}`, `{output_folder}`, `{planning_artifacts}`, `{implementation_artifacts}`, `{project_knowledge}`
- MD-based workflows execute directly — load and follow the `.md` file
- YAML-based workflows require the workflow engine — load `workflow.xml` first, then pass the `.yaml` config
- Follow step-based workflow execution: load steps JIT, never multiple at once
- Save outputs after EACH step when using the workflow engine
- The `{project-root}` variable resolves to the workspace root at runtime

## Available Agents

| Agent | Persona | Title | Capabilities |
|---|---|---|---|
| bmad-master | BMad Master | BMad Master Executor, Knowledge Custodian, and Workflow Orchestrator | runtime resource management, workflow orchestration, task execution, knowledge custodian |
| analyst | Mary | Business Analyst | market research, competitive analysis, requirements elicitation, domain expertise |
| architect | Winston | Architect | distributed systems, cloud infrastructure, API design, scalable patterns |
| dev | Amelia | Developer Agent | story execution, test-driven development, code implementation |
| pm | John | Product Manager | PRD creation, requirements discovery, stakeholder alignment, user interviews |
| qa | Quinn | QA Engineer | test automation, API testing, E2E testing, coverage analysis |
| quick-flow-solo-dev | Barry | Quick Flow Solo Dev | rapid spec creation, lean implementation, minimum ceremony |
| sm | Bob | Scrum Master | sprint planning, story preparation, agile ceremonies, backlog management |
| tech-writer | Paige | Technical Writer | documentation, Mermaid diagrams, standards compliance, concept explanation |
| ux-designer | Sally | UX Designer | user research, interaction design, UI patterns, experience strategy |

## Slash Commands

Type `/bmad-` in Copilot Chat to see all available BMAD workflows and agent activators. Agents are also available in the agents dropdown.
<!-- BMAD:END -->

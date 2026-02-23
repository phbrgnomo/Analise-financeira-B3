---
project_name: 'Analise-financeira-B3'
user_name: 'Phbr'
date: '2026-02-22'
last_updated: '2026-02-22'
sections_completed: ['technology_stack','language_rules','framework_rules','testing','code_quality','workflow_rules','critical_rules']
existing_patterns_found: 7
status: 'complete'
rule_count: 28
optimized_for_llm: true
---

# Project Context for AI Agents

_Documento enxuto com regras críticas e padrões que agentes de IA devem seguir ao implementar código neste projeto. Conteúdo otimizado para consumo por LLMs._

---

## Technology Stack & Versions

- Python: ^3.12 (Poetry) — seguir `pyproject.toml`
- SQLAlchemy: ^2.0.x
- pandas: ^2.x
- numpy: ^2.x
- typer: ^0.9.x (entrypoint: `src.main:app`)
- python-dotenv: ^1.x
- Dev: pytest (>=7.x), ruff (config via `pyproject.toml`), pre-commit

Nota: documente e justifique qualquer mudança de versão em `pyproject.toml`; confirme compatibilidade antes de alterar a versão mínima do Python (atualmente `^3.12`).

## Critical Implementation Rules

### Language-Specific (Python)

- Use `poetry` para ambiente e execução (`poetry install`, `poetry run main`).
- Evite imports pesados no startup; importe dentro de funções quando necessário.
- Siga `ruff`/`pyproject.toml` (line-length 88) e execute `pre-commit` antes de commitar.
- Nunca commitar segredos; use `.env` com `python-dotenv` para desenvolvimento local.
- Quando for implementar alguma variável de configuração, utilize `python-dotenv` e adicione a variável ao `.env.example` para referência. Nunca adicione variáveis de configuração diretamente no código ou em arquivos versionados.

### Data & Persistence

- Cada ativo tem CSV em `dados/`; a coluna `Return` é obrigatória para consumidores.
- Nunca alterar esquema de CSV/snapshots sem atualizar leitores e testes associados.
- Snapshots em `snapshots/` exigem checksum SHA256 (`<file>.checksum`); CI deve validar.

### Testing

- Cobertura: adicionar testes para novas features; seguir fixtures em `tests/conftest.py`.
- Separe unit/integration; isole rede com fixtures ou mocks.
- Execute `poetry run pytest -q` antes de abrir PR.
- Execute `tests/ci/ci_orchestration.sh` para validar ambiente CI localmente.

### Code Quality & Style

- Siga as regras definidas em `pyproject.toml` (linters/formatters) e execute `pre-commit` localmente antes de abrir PR.
- Use `type hints` em APIs públicas e em módulos novos; inclua docstrings concisas para módulos e funções públicas.
- Funções pequenas com responsabilidade única; evite aninhamento profundo e efeitos colaterais. Prefira funções puras quando aplicável.
- Tratamento de exceções: capture exceções específicas, evite `bare except`, e re-lance com contexto informativo quando necessário.
- Logging: use logging estruturado (via `src/logging_config.py`) em vez de prints. Não exponha dados sensíveis nos logs.
- Gerenciamento de recursos: use context managers para arquivos, conexões e transações; injete `engine`/dependências em vez de usar singletons globais.
- Testes: novas funcionalidades devem ter testes (unit/integration) usando as fixtures em `tests/`; isole rede com mocks/fixtures. Execute `poetry run pytest -q` localmente antes de PR.
- Documente decisões de design importantes e mudanças de dependência em `docs/sprint-reports/`; adicione testes que cobram casos-limite relevantes para alterações de comportamento.

### Imports & Dependencies

- Evitar imports globais de libs pesadas em módulos executados no startup da CLI.
- Registrar novas dependências no `pyproject.toml` e justificar em `docs/sprint-reports/`.

### Development Workflow

- Branches: tipo/ticket-descrição (seguir convenção do time).
- Rodar `pre-commit --all-files` e os testes localmente antes de PR.
- Atualizar `docs/modules/` ao alterar comportamentos ou APIs.
- Documentar implementação de stories e de alterações significativas em `docs/sprint-reports/` com motivação, decisões e resultados.

### CI

- Pipeline mínimo: `poetry install` + `poetry run pytest -q` + linters.
- Validar checksums de snapshots; falhar pipeline se divergirem.

### Critical Don't-Miss Rules

- Não modificar formatos de snapshot/CSV sem coordenação e atualização de testes.
- Não inserir credenciais em código ou arquivos versionados.
- Documentar e justificar quaisquer mudanças de dependências ou versões de Python.

---

## Referências rápidas

- Entrypoint CLI: [src/main.py](src/main.py#L1)
- Configuração: [pyproject.toml](pyproject.toml#L1)
- Locais importantes: `src/`, `dados/`, `snapshots/`, `tests/`

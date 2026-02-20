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

## IMPORTANTE

- Agentes trabalhando nesse projeto devem sempre utilizar `poetry` para execução de comandos, instalação de dependências e gerenciamento do ambiente virtual. O entrypoint definido é `main` em `src/main.py`, e deve ser invocado via `poetry run main` ou `python -m src.main` para garantir que o ambiente virtual seja ativado corretamente.
- A cada novo inicio de trabalho, o agente deve verificar a existencia dos arquivos que serão modificados ou criados, para garantir que alterações no codigo não sejam duplicadas e consistentes com o que já está presente.

## Projeto — comandos úteis

- Instalar dependências: poetry install
- Executar o entrypoint: poetry run main
- Alternativa (sem poetry): python -m src.main
- Build: poetry build
- Testes: poetry run pytest
- Lint/Format: ruff, black, pre-commit hooks

## Arquitetura (visão geral)

- Pacote principal: src/
  - src.main — entrada do aplicativo; baixa cotações, calcula retornos e imprime relatórios
  - src.dados_b3 — coleta dados (yfinance -> Yahoo) e retorna DataFrames OHLCV/Adj Close
  - src.retorno — funções para cálculo de retornos, risco, conversões e correlações; lê/espera CSVs em dados/
- Dados persistidos: pasta dados/ contendo arquivos CSV por ativo com coluna 'Return'
- Dependências principais definidas em pyproject.toml
- Entrypoint de console definido em [tool.poetry.scripts] como `main = "src.main:main"`

## Convenções chave do repositório

- Formato de data usado em main: YYYY-MM-DD (ex.: 2020-01-01)
- Ao coletar via Yahoo, ativos B3 usam sufixo .SA (ex.: PETR4 -> PETR4.SA)
- Retorno diário calculado e salvo na coluna 'Return' dos CSVs em dados/
- Cálculos anuais usam 252 períodos (dias úteis) em conv_retorno/conv_risco
- Mensagens, variáveis e comentários estão majoritariamente em PT-BR — manter consistência linguística

## Arquivos de assistente e prompts

- Existem agentes e prompts BMAD em .github/agents/ e .github/prompts/ — utilize esses templates quando gerar tarefas/fluxos automatizados
- Caso ache necessário, inicie um subagente para tarefas específicas, utilizando os prompts e fluxos pré-definidos como base, e adapte conforme o contexto da tarefa

## Documentação de referência

- O MCP `docs-mcp-server` contém documentação sobre módulos utilizados no projeto. Consulte-o para buscar a documentação mais atualizada das bibliotecas do projeto.

<!-- BMAD:END -->

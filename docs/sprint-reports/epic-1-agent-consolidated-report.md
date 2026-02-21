## Relatório Consolidado — Revisão dos Agentes (epic-1)

Data: 2026-02-21

Resumo
- Consolidei as avaliações de todos os agentes sobre o branch `epic-1`. Principais temas: correções de cálculo de retornos (anualização e divisão por zero), normalização de datas, testes faltantes e flakiness por rede, validação/checksums para snapshots, documentação quickstart incompleta, CI mínimo presente, necessidade de alinhar versão Python e incluir `poetry.lock`, melhorias de CLI (logging e saída JSON) e validação de manifest de agentes.

Ações Prioritárias (ordenadas)
1. Corrigir cálculo de retornos e tratar divisão por zero
   - Owner: `dev` (Amelia)
   - Esforço: S
   - Status: done
2. Adicionar testes unitários críticos para `retorno` e `dados_b3`
   - Owner: `qa` (Quinn) com suporte `dev`
   - Esforço: M
   - Status: done
3. Implementar checksums e job CI para validar snapshots
   - Owner: `pm` (John) / implementação: `quick-flow-solo-dev` (Barry)
   - Esforço: M
   - Status: done
4. Criar fixtures/mocks para testes de rede (reduzir flakiness)
   - Owner: `tea` (Murat) + `qa`
   - Esforço: M
5. Alinhar versão Python e gerar `poetry.lock`
   - Owner: `sm` (Bob) / execução: `quick-flow-solo-dev`
   - Esforço: S
6. Melhorar CLI: substituir `print` por `logging`, adicionar `--format json` e flags úteis
   - Owner: `ux-designer` (Sally) / implementação: `dev`
   - Esforço: M
7. Atualizar documentação quickstart e contrato de metadados do pipeline
   - Owner: `tech-writer` (Paige)
   - Esforço: S
8. Validar e automatizar manifest de agentes (`_bmad/_config/agent-manifest.csv`)
   - Owner: `agent-builder` (Bond)
   - Esforço: M
9. Criar Dockerfile mínimo e instruções de build
   - Owner: `quick-flow-solo-dev` (Barry)
   - Esforço: S
10. Spike: avaliar limites do SQLite e alternativas de escala
   - Owner: `architect` (Winston)
   - Esforço: L

Backlog Técnico (menos urgente)
- Remover índices mágicos e usar constantes nomeadas.
- Centralizar paths com `pathlib` e utilitário de root do projeto.
- Tipagem e docstrings PEP-484 nas funções públicas.
- Refatorar agentes para template padrão e adicionar validador em CI.

Checklist PR Obrigatório (gates para aceitar `epic-1`)
- Testes unitários novos e existentes passam (incl. mocks de rede).
- Lint/format passados (ruff/black) e `pre-commit` alinhado.
- `poetry.lock` incluído quando dependências mudarem.
- Job CI de checksums de snapshots verde.
- README/quickstart atualizado se CLI ou flags mudaram.
- Revisão por Dev + QA e aprovação de um reviewer de domínio de dados.

Branches/PRs sugeridos (pequenos, sequenciais)
1. `feature/epic1-fix-retorno` — correções em `src/retorno.py`, testes `tests/test_retorno.py`. (Owner: Amelia)
2. `feature/epic1-ci-checks-snapshots` — CI job para checksums, scripts de validação e `scripts/validate_agents.py`. (Owner: Barry / John)
3. `feature/epic1-docs-cli-json` — logging/`--format json` em `src/main.py`, `src/__main__.py`, e `docs/playbooks/quickstart-cli.md`. (Owner: Paige + Amelia)

Dependências e ordem de execução (resumo)
1 → 2 → 4 → 3 → 5 → 6 → 7 → 8 → 9 → 10

Riscos e Mitigações
- Flakiness por rede → mitigar com fixtures/mocks e retries com backoff.
- Divergência de ambiente (Python) → fixar versão e commitar `poetry.lock` e Dockerfile.
- Mudanças grandes em DB → rodar spike e planejar migração antes de escalonar.

Próximo passo imediato recomendado
- Criar a branch `feature/epic1-fix-retorno` e abrir PR com as correções do `retorno` e testes mínimos. Owner: `Amelia`.

Resumo final
- Relatório consolidado criado a partir das avaliações dos agentes. O foco inicial é estabilizar cálculos e testes, depois endurecer CI e docs, e por último atacar questões de escala e convenções de agentes.

agent_name: orchestrator

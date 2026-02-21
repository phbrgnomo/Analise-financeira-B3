# Playbook: Validar e Automatizar `agent-manifest.csv`

Objetivo: Garantir que `_bmad/_config/agent-manifest.csv` esteja validado, atualizado automaticamente e integrado ao CI para evitar divergências entre agentes declarados e arquivos reais.

Passos resumidos (alto nível):

1. Auditar o manifest atual e fontes de verdade
   - Localizar `_bmad/_config/agent-manifest.csv` e pastas de agentes (`_bmad/bmm/agents`, `_bmad/bmb/agents`, `_bmad/core/agents`, etc.)
   - Identificar colunas obrigatórias (id, name, path, version, owner, description, active)

2. Definir esquema do manifest
   - Criar `docs/agent_manifest_schema.json` (JSON Schema) com campos e tipos
   - Documentar convenções em `docs/playbooks/agent-manifest-playbook.md`

3. Implementar validador e gerador
   - Script `scripts/validate_agent_manifest.py`: valida CSV contra JSON Schema e verifica existência dos arquivos `path`
   - Script `scripts/generate_agent_manifest.py`: varre pastas de agentes e gera/atualiza o CSV (modo `--dry-run` e `--apply`)

4. Adicionar testes
   - `tests/test_agent_manifest_validation.py`: casos positivos/negativos e integração com `scripts/generate_agent_manifest.py`

5. Integrar com CI
   - Adicionar job `validate-agent-manifest` que executa o validador e falha em divergências

6. Documentação e PR
   - Atualizar README/PLAYBOOK com instruções de uso, explicar como rodar localmente e como abrir PRs de agentes
   - Criar branch `feature/agent-manifest-automation` e abrir PR com mudanças

Prioridade e estimativa
- Esforço: M
- Owner: `agent-builder` (Bond)

Entregáveis
- `docs/agent_manifest_schema.json`
- `scripts/validate_agent_manifest.py`
- `scripts/generate_agent_manifest.py`
- `tests/test_agent_manifest_validation.py`
- CI job (`.github/workflows/validate-agent-manifest.yml`)

Próximo passo imediato
- Executar auditoria local do manifest e iniciar o script gerador em modo `--dry-run`.

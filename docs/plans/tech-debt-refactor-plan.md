# Plano de Implementação — Backlog Técnico (refactor)

Objetivo: reduzir dívida técnica nas três frentes listadas — substituir índices mágicos por constantes nomeadas, centralizar manipulação de paths com `pathlib` e utilitário de root do projeto, e adicionar tipagem PEP-484 + docstrings nas funções públicas.

Resumo das etapas:

1. Auditoria de Código (scan)
   - Rodar busca por padrões: números literais usados como índices, strings de path concatenadas, e funções públicas sem anotações de tipos.
   - Produzir relatório com arquivos e trechos a alterar.

2. Remover índices mágicos → constantes nomeadas
   - Criar `src/constants.py` (ou `src/_constants.py`) com nomes claros (ex.: `COL_TICKER = 0`, `DEFAULT_TIMEOUT = 30`).
   - Substituir ocorrências nos módulos: `src/retorno.py`, `src/dados_b3.py`, `src/adapters/*`, `src/etl/*`.
   - Adicionar testes que validem comportamentos que dependiam dos índices (evitar regressões).

3. Centralizar paths com `pathlib` e utilitário de root
   - Criar `src/paths.py` com função `project_root()` e paths comuns (`SNAPSHOTS_DIR`, `RAW_DIR`, `METADATA_DIR`).
   - Refatorar uso de strings para `Path` em `scripts/`, `src/`, `docs/playbooks` exemplos quando aplicável.
   - Atualizar docstrings e quickstart com exemplos `pathlib` quando necessário.

4. Tipagem PEP-484 e docstrings
   - Priorizar funções públicas de módulos `src/retorno.py`, `src/dados_b3.py`, `src/main.py` e adaptadores.
   - Adicionar anotações de tipo, `from typing import Optional, List, Dict` e docstrings compatíveis com numpydoc/Google style.
   - Adicionar `mypy` (ou `ruff`/`pyright`) em dev-deps e CI; criar config `mypy.ini` ou `pyproject.toml` section.

5. Testes e CI
   - Atualizar/Adicionar testes unitários que cubram as mudanças.
   - Adicionar job de checagem estática (`mypy`/`ruff`) em `.github/workflows/ci.yml`.

6. Lançamento e PR
   - Quebrar trabalho em pequenos PRs por área (constants, paths, typing) para facilitar revisão.
   - Checklist do PR: testes passam, lint/format OK, `pyproject.toml` atualizado se necessário, changelog.

Estimativa e owners
- Esforço total estimado: M (médio). Pode ser dividido em 3 PRs pequenos (cada PR S-M).
- Owner sugerido: `dev` (Amelia) com revisão `qa` e `architect` para mudanças de arquitetura.

Próximo passo imediato
- Executar a auditoria de código (passo 1) e retornar o relatório com locais alvo para alteração.

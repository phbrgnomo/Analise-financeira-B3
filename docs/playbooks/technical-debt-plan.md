# Plano: Remover dívida técnica — índices mágicos, paths e tipagem

Objetivo: Eliminar pontos de fragilidade e melhorar a manutenção do código através de três ações: substituir índices mágicos por constantes nomeadas, centralizar gerenciamento de paths com `pathlib` e um utilitário de root do projeto, e aplicar tipagem e docstrings PEP-484 nas funções públicas.

Fases e tarefas

1) Inventário e métricas (1 dia)
   - Executar uma varredura do código para localizar usos de índices literais, concatenações de paths e funções públicas sem tipagem/docstrings.
   - Ferramenta: `grep`/`ruff`/`pylint` e revisão manual em `src/` e `_bmad/`.
   - Entregável: `docs/technical-debt/inventory.md` com lista de locais e estimativa de impacto.

2) Substituir índices mágicos por constantes nomeadas (2-3 dias)
   - Identificar constantes por módulo (por ex.: `DEFAULT_PAGE_SIZE`, `SNAPSHOT_COLUMN_INDEX`).
   - Criar módulo `src/constants.py` (ou `src/_constants.py`) e mover constantes relevantes.
   - Refatorar arquivos consumidores para importar constantes em vez de números mágicos.
   - Adicionar testes pequenos que assegurem os valores das constantes (para evitar regressões silenciosas).

3) Centralizar paths com `pathlib` e utilitário de root (1-2 dias)
   - Criar `src/paths.py` com função `project_root()` e constantes Path para `snapshots/`, `dados/`, `docs/`, etc.
   - Refatorar código para usar `paths.SNAPSHOTS_DIR / f"{ticker}_snapshot.csv"` em vez de strings formatadas.
   - Atualizar tests e fixtures para usar o utilitário (ex.: `tmp_path` joining).

4) Tipagem e docstrings PEP-484 nas funções públicas (2-4 dias)
   - Priorizar funções de API pública: `src/retorno.py`, `src/dados_b3.py`, `src/main.py`.
   - Adicionar tipagem gradual (Começar com anotações de entrada/saída simples, evitar complexidade de tipos genéricos inicialmente).
   - Adicionar docstrings no formato Google/NumPy/PEP-257 (consistente com estilo do projeto).
   - Executar `mypy --ignore-missing-imports` em modo incremental (opcional adicionar `mypy` ao dev-deps).

5) Revisão, CI e merge (1 dia)
   - Abrir PRs pequenos por área (constantes, paths, tipagem) e rodar pipeline completo.
   - Exigir aprovação de `dev` + `qa` e garantir `ruff/black` passando.

Responsáveis e estimativas
- Owner: `dev` (Amelia)
- Revisores: `qa` (Quinn), `architect` (Winston)
- Esforço total estimado: 1-2 semanas (dependendo do tamanho do código e alcance incremental)

Observações de implementação
- Faça commits pequenos e atômicos por tipo de mudança (ex.: `refactor: extract SNAPSHOT paths to paths.py`).
- Use `grep -nE "\b[0-9]{1,3}\b"` com cuidado; prefira análise semântica manual para evitar falsos positivos.
- Ao introduzir `src/paths.py` e `src/constants.py`, exporte nomes públicos com `__all__` e documente-os em `README.md`.

Próximo passo imediato
- Executar a varredura de inventário e criar `docs/technical-debt/inventory.md`.

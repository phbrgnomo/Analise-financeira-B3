# Story 0.1: Inicializar pyproject.toml e dependências mínimas

Status: ready-for-dev

## Story
Como Desenvolvedor(a),
quero um `pyproject.toml` mínimo com dependências e dev-dependências declaradas,
para que eu possa instalar e executar o projeto e os testes de forma consistente usando o `poetry`.

## Acceptance Criteria
1. Dado um checkout limpo do repositório, ao executar `poetry install` (ou `poetry install --no-dev` para CI), as dependências de runtime e desenvolvimento são instaladas sem erros.
2. `poetry run main --help` (ou `python -m src.main --help`) exibe a saída de ajuda da CLI.
3. O `pyproject.toml` contém versões mínimas/pinadas para os principais pacotes (`pandas`, `sqlalchemy`, `typer`, `pytest`) e documenta quaisquer restrições importantes.

## Tasks / Subtasks
- [x] Adicionar `pyproject.toml` com dependências de runtime: `pandas`, `sqlalchemy`, `typer`, `python-dotenv`.
- [x] Adicionar dev-dependencies: `pytest`, `black`, `ruff`, `pre-commit` e configurar hooks básicos do pre-commit.
- [x] Adicionar script de entrypoint `main` em `src/main.py` e verificar `poetry run main --help`.
- [x] Documentar comandos de quickstart no README.md (instalação, execução, testes).
- [x] Documentar o que foi implantado nessa etapa conforme o FR28 (`docs/planning-artifacts/prd.md`)

## Dev Notes

- Mantenha as versões conservadoras e explicitamente fixadas para garantir reprodutibilidade nas fases iniciais.
- Siga o layout do projeto conforme descrito em `docs/planning-artifacts/architecture.md` na seção ## Project Structure & Boundaries.
- Garanta compatibilidade com Python 3.14, conforme indicado nos artefatos de planejamento.

### Project Structure Notes

- Coloque o `pyproject.toml` na raiz do repositório.
- Adicione o esqueleto da pasta `tests/` e a subpasta `tests/fixtures/` para CSVs de exemplo (ver `docs/planning-artifacts/epics.md`).

### References

- Source: [docs/planning-artifacts/epics.md](docs/planning-artifacts/epics.md)
- Architecture: [docs/planning-artifacts/architecture.md](docs/planning-artifacts/architecture.md)
- Sprint status: [docs/implementation-artifacts/sprint-status.yaml](docs/implementation-artifacts/sprint-status.yaml)

## Dev Agent Record

- Implementações realizadas nesta sessão:
	- `pyproject.toml` atualizado com dependências runtime e dev-dependencies.
	- `src/main.py` convertido para CLI mínima com `typer` (importações sob demanda para permitir `--help`).
	- `tests/test_cli.py` adicionado e `pytest` executado com sucesso (2 passed).
	- `.pre-commit-config.yaml` adicionado; hooks instalados e executados, correções aplicadas.
	- `README.md` atualizado com seção Quickstart (instalação, execução, testes, pre-commit).
	- `docs/implementation-artifacts/sprint-status.yaml` atualizado para `in-progress`.

Arquivos alterados nesta sessão:
    - `pyproject.toml`
    - `src/main.py`
    - `tests/test_cli.py`
    - `.pre-commit-config.yaml`
    - `README.md`
    - `docs/implementation-artifacts/sprint-status.yaml`


### Agent Model Used

GPT-5 mini

### Completion Notes List

- Ultimate context engine analysis completed for story foundation.

### File List

- `pyproject.toml` (create)
- `src/main.py` (verify entrypoint)
- `README.md` (update quickstart)
- `tests/` (skeleton and fixtures)



Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/104

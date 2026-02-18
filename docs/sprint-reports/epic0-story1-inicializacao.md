---
title: Epic 0 Story 1 Report — Quickstart e Inicialização
date: 2026-02-17
author: Phbr / Dev Agent
tags: [epic-0, story-1 quickstart, implementation]
---

# Phase 1 — Implementação e Checklist (relatório FR28)

Resumo: este relatório documenta as alterações e artefatos entregues na primeira sessão de implementação do story `0-1-inicializar-pyproject-toml-e-dependencias-minimas`.

## Objetivo
- Garantir que o repositório possua um `pyproject.toml` mínimo capaz de instalar dependências, um `entrypoint` CLI (`main`) funcional, testes básicos e hooks `pre-commit` para qualidade inicial.

## O que foi implementado

- `pyproject.toml`
  - Dependências runtime adicionadas: `sqlalchemy`, `typer`, `python-dotenv` (além de `pandas`, `numpy`, `pandas-datareader`).
  - Dev-dependencies adicionadas: `pytest`, `black`, `ruff`, `pre-commit`.
  - Script entrypoint corrigido para `main = "src.main:app"`.

- `src/main.py`
  - Convertido para CLI com `typer` (`app`) e importações pesadas movidas para dentro do comando para permitir `--help` sem carregar dependências runtime.
  - Tratamento de exceções melhorado (não usar `except:` cru).

- Testes
  - `tests/test_cli.py` adicionado: valida que o CLI responde a `--help` (teste rápido que não requer providers externos).
  - `poetry run pytest` executado com sucesso (2 testes passando após formatação).

- Pre-commit
  - `.pre-commit-config.yaml` adicionado com hooks: `black`, `ruff`, `pre-commit-hooks` (end-of-file-fixer, trailing-whitespace).
  - Hooks instalados e executados; código reformatado e issues de lint corrigidas.

- Documentação
  - `README.md` atualizado com seção `Quickstart` (instalação via `poetry`, execução CLI, rodar testes, habilitar pre-commit).
  - `docs/implementation-artifacts/0-1-inicializar-pyproject-toml-e-dependencias-minimas.md` atualizado para marcar subtasks concluídas e registrar File List.
  - `docs/sprint-reports/epic0-story1-inicializacao.md` (este arquivo) adicionado como relatório FR28.

- Sprint status
  - `docs/implementation-artifacts/sprint-status.yaml` atualizado para marcar a story como `in-progress`.

## Como reproduzir localmente

1. Instalar dependências e ambiente:

```bash
poetry lock
poetry install
```

2. Verificar ajuda do CLI:

```bash
poetry run main --help
# ou
python -m src.main --help
```

3. Rodar testes:

```bash
poetry run pytest -q
```

4. Instalar e rodar pre-commit (opcional):

```bash
poetry run pre-commit install
poetry run pre-commit run --all-files
```

## Arquivos modificados nesta sessão

- pyproject.toml
- src/main.py
- src/retorno.py (mensagens de erro e tratamento de exceção)
- tests/test_cli.py
- .pre-commit-config.yaml
- README.md
- docs/implementation-artifacts/0-1-inicializar-pyproject-toml-e-dependencias-minimas.md
- docs/implementation-artifacts/sprint-status.yaml
 - docs/sprint-reports/epic0-story1-inicializacao.md

## Decisões e justificativas

- Mover imports pesados para dentro do comando CLI: permite que `--help` seja exibido sem exigir todas as dependências runtime, útil para UX de desenvolvedor e CI inicial.
- Preferir `except Exception as e` em vez de `except:` para melhor rastreabilidade e conformidade com linters (`ruff`).
- Incluir `typer` para prover uma CLI com `--help` consistente e fácil de estender com subcomandos.

## Próximos passos recomendados

1. Implementar `pre-commit` hooks adicionais e um profile `poetry.group.dev.dependencies` (migrar dev-dependencies conforme aviso do Poetry).
2. Implementar `docs/playbooks/quickstart-ticker.md` com um quickstart de ingest para um ticker de exemplo (mockado em CI).
3. Criar módulos `db` e `pipeline` com contratos `db.write_prices`, `pipeline.ingest` e adicionar testes unitários/integração básicos.
4. Adicionar fixture de dados em `tests/fixtures/` e exemplo de CSV de snapshot em `tests/fixtures/sample_snapshot.csv`.

## Notas de rastreabilidade (issue/PR)

- Issue relacionada: https://github.com/phbrgnomo/Analise-financeira-B3/issues/104

---

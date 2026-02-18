# Implantação — Story 0.3: Pre-commit (black + ruff)

Data: 2026-02-17

Resumo
-----

Implementado e configurado o conjunto de ferramentas de qualidade de código para o projeto:

- `.pre-commit-config.yaml` com hooks para `black`, `ruff` e alguns hooks básicos (`end-of-file-fixer`, `trailing-whitespace`).
- Atualização de `pyproject.toml` com configurações de `tool.black` e `tool.ruff`.
- Workflow GitHub Actions: `.github/workflows/ci.yml` que executa `pre-commit`, `black --check` e `ruff check`.
- Correções automáticas e ajustes manuais aplicados para satisfazer limites de linha (`E501`) e regras de formatação.

Arquivos modificados/criados
---------------------------

- .pre-commit-config.yaml (adicionado)
- pyproject.toml (atualizado: `tool.black`, `tool.ruff`)
- .github/workflows/ci.yml (adicionado)
- src/main.py (ajustes de comentários/format)
- src/retorno.py (ajustes de comentários/format)
- tests/conftest.py (quebra de string SQL longa)
- tests/test_cli.py (redução de docstring/ajuste de comentários)
- docs/implementation-artifacts/0-3-adicionar-pre-commit-com-black-e-ruff.md (atualizado com registro de ações)

Comandos para reproduzir localmente
----------------------------------

1. Instalar dependências via `poetry` (ambiente de desenvolvimento):

```bash
poetry install
```

2. Instalar hooks (opcional local):

```bash
poetry run pre-commit install
```

3. Executar hooks em todos os arquivos (aplica correções automáticas onde configurado):

```bash
poetry run pre-commit run --all-files
```

4. Executar verificações específicas (sem aplicar mudanças):

```bash
poetry run black --check .
poetry run ruff check .
```

Verificações realizadas nesta sessão
-----------------------------------

- `poetry run pre-commit run --all-files` (executado) — inicialmente `ruff` reportou erros `E501` (linhas > 88 chars).
- `poetry run ruff check --fix .` e ajustes manuais foram aplicados para resolver os `E501`.
- Reexecutado `pre-commit` — todos os hooks passaram.
- `poetry run pytest -q` — testes passaram (2 passed, 10 warnings).

Próximos passos recomendados
---------------------------

- Commitar estas alterações (já preparado neste commit).
- Atualizar `README.md` caso queira documentar comandos adicionais ou versão mínima das ferramentas.
- Opcional: abrir PR para revisão de pares.

Notas de implementação
---------------------

- `ruff` está configurado via `pyproject.toml` (`tool.ruff`). Algumas opções top-level foram migradas para a seção `lint` em versões recentes; considerar adaptar conforme futuras recomendações do `ruff`.
- Mantivemos `line-length = 88` para compatibilidade com `black`.

Contato
-------

Para dúvidas, revisar o histórico de commits desta sessão ou falar com o autor do PR/commit.

# Implantação Story 1-11 — Definir esquema canônico de dados

Resumo da implantação

- Story: 1-11 — Definir esquema canônico de dados e documentação do modelo (schema + examples)
- Autor das mudanças: phbr
- Commits principais: 514f81b, 76531bb

O que foi implementado

- Criado `docs/schema.yaml` com `schema_version: 1` e notas semânticas por coluna.
- Adicionada documentação em `docs/schema.md` explicando campos, versionamento e migrações.
- Inclusão de `dados/examples/ticker_example.csv` como exemplo referenciado pela documentação.
- Adicionado teste unitário `tests/test_schema.py` que valida ordem das colunas e formatos essenciais (date, fetched_at, raw_checksum).
- Adicionada referência ao esquema em `docs/implementation-artifacts/1-1-implementar-interface-de-adapter-e-adaptador-yfinance-minimo.md`.
- Atualizado `docs/implementation-artifacts/sprint-status.yaml` com o status desta story (ready-for-dev).

Resultados de testes

- Comando executado: `poetry run pytest -q tests/test_schema.py`
- Resultado: 1 teste executado — passou.

Recomendações pós-implantação

- Incluir validação de DataFrame (pandera) para validar snapshots no pipeline/CI.
- Adicionar passo de verificação de schema na CI para garantir conformidade dos snapshots.

# Implantação Story 1-11 — Definir esquema canônico de dados

Resumo da implantação

- Story: 1-11 — Definir esquema canônico de dados e documentação do modelo (schema + examples)
- Autor das mudanças: phbr
- Commits principais: 514f81b, 76531bb

Commits principais (no histórico recente):
- f2f14dd — feat: adicionar esquema canônico em formato JSON e atualizar testes de validação
- 1000940 — fix: corrigir caminho do arquivo de exemplo no teste de validação do esquema
- ec1ce91 — feat: substituir pandas_datareader por yfinance e atualizar documentação

O que foi implementado

- Criado `docs/schema.json` com `schema_version: 1` e notas semânticas por coluna.
- Adicionada documentação em `docs/schema.md` explicando campos, versionamento e migrações.
- Inclusão de `dados/examples/ticker_example.csv` como exemplo referenciado pela documentação.
- Adicionado teste unitário `tests/test_schema.py` que valida ordem das colunas e formatos essenciais (date, fetched_at, raw_checksum).
- Adicionada referência ao esquema em `docs/implementation-artifacts/1-1-implementar-interface-de-adapter-e-adaptador-yfinance-minimo.md`.
- Atualizado `docs/implementation-artifacts/sprint-status.yaml` com o status desta story (ready-for-review).

Observação sobre caminhos reais:
- O artefato de esquema presente no repositório está em `docs/schema.json` (não `docs/schema.yaml`).
- O arquivo de exemplo de dados está em `dados/samples/ticker_example.csv`.
- O teste `tests/test_schema.py` referencia `docs/schema.json` e `dados/samples/ticker_example.csv` (teste passou).

Ações tomadas para consistência:
- Normalizada a documentação e os relatos da story para apontar para `docs/schema.json` e `dados/samples/ticker_example.csv`.
- Atualizada a seção de File List da story para refletir os caminhos reais presentes no repositório.

Resultados de testes

- Comando executado: `poetry run pytest -q tests/test_schema.py`
- Resultado: 1 teste executado — passou.

Verificações adicionais executadas
- `git status --porcelain` e `git diff --name-only` para identificar mudanças locais e commits relacionados.
- Conferido que os arquivos existem em HEAD: `docs/schema.json`, `docs/schema.md`, `dados/samples/ticker_example.csv`, `tests/test_schema.py`, `docs/implementation-artifacts/sprint-status.yaml`, `docs/sprint-reports/1-11-implantacao.md`.

Recomendações pós-implantação

- Incluir validação de DataFrame (pandera) para validar snapshots no pipeline/CI.
- Adicionar passo de verificação de schema na CI para garantir conformidade dos snapshots.

Recomendações adicionais (curto prazo)
- Adicionar um pequeno job de CI que valide que `docs/schema.json` e o CSV de exemplo estão consistentes (mesmos nomes e ordem de colunas).
- Documentar no README ou em `docs/schema.md` qual arquivo é a "fonte da verdade" (atualmente `docs/schema.json`) para evitar confusão futura.

Decisões e justificativas

- Fonte da verdade do esquema: adotamos `docs/schema.json` como artefato canônico nesta implementação. Justificativa: já havia sido criado e os testes existentes (`tests/test_schema.py`) referenciam JSON; manter JSON evita duplicação e regressões imediatas.

- Local dos exemplos: os CSVs de exemplo foram colocados em `dados/samples/` (não `dados/examples/`). Justificativa: repositório já usa `dados/samples/` para artefatos usados por testes e fixtures; manter esse local facilita reprodução por fixtures existentes.

- Formato de validação no teste: `tests/test_schema.py` faz validações simples de ordem de colunas e formatos (regex) em vez de usar `pandera`. Justificativa: solução leve e sem dependências adicionais para CI rápido; recomendamos `pandera` para validações mais robustas em pipeline.

- Não gerar `docs/schema.yaml` automaticamente: optamos por não criar um `schema.yaml` adicional para evitar manutenção de múltiplas fontes. Justificativa: evitar divergência entre JSON e YAML; se for necessário fornecer YAML por compatibilidade, gerar a partir do JSON e documentar o processo.

- Atualização de status do sprint: `docs/implementation-artifacts/sprint-status.yaml` foi atualizado para refletir `1-11` como `ready-for-review`. Justificativa: seguir o fluxo de trabalho do projeto e permitir integração com rastreamento de sprint por arquivo.

Essas decisões visam minimizar trabalho manual e risco de divergência entre testes e documentação enquanto preservam um caminho claro para evolução (ex.: migrar para validação mais forte com `pandera` e adicionar job de CI específico).

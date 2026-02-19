---
project_name: 'Analise-financeira-B3'
user_name: 'Phbr'
date: '2026-02-18'
sections_completed: ['technology_stack','language_rules','testing','code_quality','workflow_rules','critical_rules','party_mode_updates']
existing_patterns_found: 7
---

# Project Context for AI Agents

_Arquivo enxuto com regras críticas e padrões que agentes de IA devem seguir ao implementar código neste projeto._

---

## Technology Stack & Versions

- Python: ^3.14 (Poetry)
- numpy: ^2.3.2
- pandas: ^2.3.2
- pandas-datareader: ^0.10.0
- SQLAlchemy: ^2.0.18
- typer: ^0.9.0 (entrypoint: `src.main:app`)
- python-dotenv: ^1.0.0
- Dev: pytest ^7.4.0, black ^24.10.0, ruff ^0.14.14, pre-commit ^3.3.0

Observação: seguir estritamente as versões definidas em `pyproject.toml`; documente e justifique qualquer mudança de versão.

## Critical Implementation Rules

### Regras Específicas de Python

- Use `poetry` para instalação e execução (`poetry install`, `poetry run main`).
- Evite impor dependências no import global: importe módulos pesados dentro de funções quando apropriado (padrão já aplicado em `src/main.py`).
- Respeite convenções de formato (`black`, `ruff`) com length=88 antes de commitar; execute `pre-commit` localmente.
- Nunca comitar segredos; use `.env` (não versionar) e `python-dotenv` para carregamento local.

### Regras de Dados e Persistência

- Arquivo CSV por ativo em `dados/` com coluna `Return` obrigatória para consumidores.
- Não altere o esquema CSV sem atualizar todas as funções que leem `dados/` (ex.: `src/retorno.py`, `src/main.py`).

### Snapshots & Checksums

- Todos os snapshots em `snapshots/` devem ter um arquivo de checksum SHA256 associado (`<file>.checksum`).
- CI deve verificar checksums: falhar o pipeline se checksum não corresponder ao conteúdo do snapshot.
- Processo de validação sugerido (exemplo):

```bash
sha256sum snapshots/PETR4_snapshot.csv | cut -d' ' -f1 > snapshots/PETR4_snapshot.csv.checksum
# comparar com o conteúdo existente em PETR4_snapshot.csv.checksum
```

### Testes

- Novas funcionalidades devem incluir testes `pytest` compatíveis com fixtures existentes (`tests/conftest.py`).
- Separe testes unitários e de integração; mocks devem isolar chamadas de rede (use fixtures existentes para snapshots locais).
- Executar suíte de testes antes de abrir PR: `poetry run pytest -q`.

### Testes e Isolamento de Rede

- Ao rodar testes que tocam rede, usar `--no-network` ou fixtures que simulam/fornecem snapshots locais.
- Fixtures em `tests/` já suportam cenários sem rede; prefira esses para testes de CI.

### Estilo e Qualidade

- Siga as configurações em `pyproject.toml` para `black` e `ruff` (line-length 88).
- Prefira nomes descritivos em PT-BR para mensagens e comentários, mantendo consistência linguística do repositório.
- Funções devem ser pequenas e com responsabilidade única; evitar lógica profundamente aninhada.

### Imports e Gerenciamento de Dependências

- Evitar imports globais de bibliotecas pesadas em módulos executados no startup da CLI; preferir imports locais dentro de comandos/funções, como já praticado em `src/main.py`.
- Qualquer adição de dependência deve ser registrada no `pyproject.toml` com justificativa em `docs/`.

### Workflow de Desenvolvimento

- Branches: siga convenções do time (nomear branch com tipo/ticket-descrição quando aplicável).
- Use `pre-commit` e formatação automática antes de commitar.
- Inclua testes e atualize `docs/` quando mudanças de comportamento ou APIs forem introduzidas.

### Regras de CI

- CI deve executar `poetry install --no-dev` (smoke) e `poetry install` + `poetry run pytest -q` nos pipelines principais.
- `pre-commit` deve rodar e passar locais antes de abrir PR; o pipeline pode rodar linters adicionais (ruff/black).

### Regras Críticas "Não Erre"

- Não modificar o formato dos snapshots nem remover a coluna `Return` sem atualização coordenada dos consumidores.
- Não introduzir endpoints que dependam de credenciais versionadas.
- Documentar qualquer dependência nova ou atualização de versão no `pyproject.toml` e em `docs/`.

- Especificar versão mínima do Python: `Python >= 3.14.0` (documentar incompatibilidades conhecidas de dependências nativas se houver).
- Não substituir formatos de snapshot/CSV sem atualização dos manifests e dos testes que validam checksums.

---

## Referências rápidas

- Entrypoint CLI: `src/main.py` (Typer)
- Configuração de dependências: `pyproject.toml`
- Locais importantes: `src/`, `dados/`, `snapshots/`, `tests/`

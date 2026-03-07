---
project_name: 'Analise-financeira-B3'
user_name: 'Phbr'
date: '2026-02-22'
sections_completed: ['technology_stack','language_rules','framework_rules','testing','code_quality','workflow_rules','critical_rules']
existing_patterns_found: 7
status: 'complete'
rule_count: 29
optimized_for_llm: true
last_updated: '2026-03-05'
---

# Project Context for AI Agents

_Documento enxuto com regras críticas e padrões que agentes de IA devem seguir ao implementar código neste projeto. Conteúdo otimizado para consumo por LLMs._

---

## Technology Stack & Versions

- Python: ^3.12 (Poetry) — seguir `pyproject.toml`
- sqlite3 (standard library) — persistência principal
- SQLAlchemy: ^2.0.x (dependência declarada, mas não usada diretamente no core; pode ser removida em sprint futuro)
- pandas: ^2.x
- numpy: ^2.x
- typer: ^0.9.x (entrypoint: `src.main:app`)
- python-dotenv: ^1.x
- Dev: pytest (>=7.x), ruff (config via `pyproject.toml`), pre-commit

Nota: documente e justifique qualquer mudança de versão em `pyproject.toml`; confirme compatibilidade antes de alterar a versão mínima do Python (atualmente `^3.12`).

## Critical Implementation Rules

### Language-Specific (Python)

- Use `poetry` para ambiente e execução (`poetry install`, `poetry run main`).
- Evite imports pesados no startup; importe dentro de funções quando necessário.
- Siga `ruff`/`pyproject.toml` (line-length 88) e execute `pre-commit` antes de commitar.
- Nunca commitar segredos; use `.env` com `python-dotenv` para desenvolvimento local.
- Quando for implementar alguma variável de configuração, utilize `python-dotenv` e adicione a variável ao `.env.example` para referência. Nunca adicione variáveis de configuração diretamente no código ou em arquivos versionados.

### Framework-Specific Rules

- CLI: o projeto usa `typer` para a CLI (`src/main.py`). Mantenha comandos leves; evite imports pesados no topo do módulo da CLI — importe dentro da função do comando quando necessário.
- Adapter Factory: siga a fábrica de adapters em `src/adapters/factory.py`. Sempre obter instâncias via `get_adapter()` ou `register_adapter()`; não introduza caminhos alternativos de criação de adapters sem atualizar `docs/modules/adapter-guidelines.md`.

  ```python
  # exemplo mínimo de uso
  from src.adapters.factory import get_adapter, register_adapter

  # pegar um adapter já registrado (yfinance é um adapter builtin)
  yf = get_adapter("yfinance")
  df = yf.fetch("PETR4.SA", start="2020-01-01")

  # registrar um adapter customizado (veja docs/modules/adapter-guidelines.md
  # para a assinatura de BaseAdapter e requisitos de retorno)
  class MyAdapter(BaseAdapter):
      def fetch(self, ticker: str, **kwargs) -> pandas.DataFrame:
          ...

  register_adapter("mykey", MyAdapter)  # disponibiliza get_adapter("mykey")
  ```


- **Testes de exemplo**: aqui está um padrão de fixtures que você pode copiar
  para `tests/conftest.py` e reutilizar nos seus `test_*.py`.

  ```python
  # tests/conftest.py
  import pytest
  import sqlite3
  from unittest.mock import patch
  import pandas as pd

  @pytest.fixture
  def yf_mock():
      """Simula a chamada a yfinance.download usada por adapters builtin."""
      with patch("yfinance.download") as mock:
          # configure um DataFrame de exemplo retornado pelo mock
          mock.return_value = pd.DataFrame({"date": ["2020-01-01"], "close": [100]})
          yield mock

  @pytest.fixture
  def tmp_db():
      """Conexão SQLite in-memory que pode ser injetada nos helpers."""
      conn = sqlite3.connect(":memory:")
      yield conn
      conn.close()
  ```

  Um teste concreto usando essas fixtures poderia ser:

  ```python
  # tests/test_etl.py
  def test_process_etl_with_mock(yf_mock, tmp_db):
      from src.adapters.factory import get_adapter
      from src.db import write_prices, compute_raw_checksum

      adapter = get_adapter("yfinance")
      df = adapter.fetch("PETR4")  # yfinance.download interceptado pelo yf_mock
      assert not df.empty

      # passe a conexão in-memory ao seu código
      # supondo uma função process_etl(ticker, conn)
      process_etl("PETR4", conn=tmp_db)
      cur = tmp_db.cursor()
      cur.execute("SELECT COUNT(*) FROM prices")
      assert cur.fetchone()[0] >= 0
  ```


- ETL/Adapters: módulos em `src/etl/` e `src/adapters/` devem aceitar injeção de `conn`/dependências para facilitar testes. Preserve a lógica de `raw_checksum` e idempotência ao gravar no DB.

  ```python
  import sqlite3
  from contextlib import contextmanager
  from src.adapters.factory import get_adapter
  from src.db import write_prices, compute_raw_checksum

  def process_etl(ticker: str, conn: sqlite3.Connection):
      # conn é injetado pelo chamador (tests, CLI, etc.)
      with conn:  # começa/commita transação automáticamente
          adapter = get_adapter("yfinance")
          df = adapter.fetch(ticker)

          raw_checksum = compute_raw_checksum(df)
          # write_prices é idempotente e utiliza raw_checksum internamente
          write_prices(df, conn=conn, raw_checksum=raw_checksum)
  ```

  A documentação em `docs/modules/adapter-guidelines.md` descreve o contrato
  que cada adapter deve seguir (métodos obrigatórios, tratamento de erros,
  exemplos de teste), o que garante que `get_adapter` sempre retorne um objeto
  com a interface esperada.

- SQLite/DB: a persistência canônica é `sqlite3` (arquivo padrão `dados/data.db`). Use context managers para transações e permita sobrepor `conn` em testes/fixtures.
- SQLAlchemy: presente como dependência em alguns lugares; verifique uso antes de introduzir sessões globais — prefira sessões explícitas e injeção de engine.
- Sem servidor web: não adicione frameworks web (Flask/FastAPI) a menos que haja justificativa clara e documentação de compatibilidade e testes.
- Testes de integração de adapters: ao usar `yfinance` ou APIs externas, mocke as chamadas em `tests/` usando as fixtures disponíveis; documente alterações no comportamento em `docs/sprint-reports/`.

### Data & Persistence

- Cada ativo tem CSV em `dados/`; a coluna `Return` é obrigatória para consumidores.
- Nunca alterar esquema de CSV/snapshots sem atualizar leitores e testes associados.
- Snapshots em `snapshots/` exigem checksum SHA256 (`<file>.checksum`); CI deve validar.
- Qualquer PR que altere arquivos versionados em `snapshots/` deve atualizar
  também `snapshots/checksums.json` usando `scripts/validate_snapshots.py --update`
  e registrar a justificativa no PR.
- Scripts utilitários vivem em `scripts/` e servem como helpers de linha de comando (ex.: `validate_snapshots.py`, `init_ingest_db.py`). Leia o cabeçalho antes de alterar ou reutilizar.

### Testing

- Cobertura: adicionar testes para novas features; siga as fixtures em `tests/conftest.py`.
- Organização: coloque testes unitários em `tests/` com nomes `test_*.py`; use subpastas para agrupamento por módulo.
- Separe unit/integration: marque testes de integração com `@pytest.mark.integration` e execute-os separadamente no CI.
- Mocks: isole chamadas de rede (ex.: `yfinance`) usando fixtures, `responses`, `requests-mock` ou `pytest` monkeypatch; nunca depender de rede em testes unitários.
- DB em testes: prefira `sqlite3` in-memory ou um `tmp_path` DB; injete `conn` para permitir isolamento e rollback entre testes.
- Snapshots: valide checksums de snapshots em fixtures; testes que usam `snapshots/` devem carregar via helpers existentes e impedir escrita acidental.
- Recursos temporários: use `tmp_path`/`tmp_path_factory` para arquivos temporários e garanta cleanup automático.
- Testes lentos: marque testes lentos com `@pytest.mark.slow` e exclua-os do pipeline padrão, exceto quando necessário.
- CI: Pipeline deve executar linters e `poetry run pytest -q` (unit + smoke); integração e testes lentos podem ser jobs separados.
- Executar localmente: use `poetry run pytest -q` e `poetry run pre-commit --all-files` antes de abrir PR.

### Code Quality & Style

- Lint & Formatting: siga `pyproject.toml` (ruff) e mantenha `line-length: 88`. Execute `pre-commit --all-files` localmente antes de PR; falhas de lint devem bloquear merge.
- Tipagem: use `type hints` em APIs públicas e novos módulos; adicione docstrings concisas para módulos e funções públicas.
- Pequenas funções: prefira funções pequenas e puras quando possível; evite aninhamento profundo e efeitos colaterais.
- Exceções: capture exceções específicas e evite `bare except`. Use `raise from` para manter contexto de erros.
- Logging: utilize `src/logging_config.py` para logging estruturado; não use `print()` em produção e não logue dados sensíveis.

  Exemplo rápido de uso:

  ```python
  from src.logging_config import get_logger

  logger = get_logger(__name__)
  logger.info("iniciando processamento", extra={"ticker": "PETR4", "period": "1y"})
  ```

  o factory `get_logger` retorna um logger configurado com o formatter
  JSON do projeto; o parâmetro `extra` permite anexar campos estruturados
  que aparecem no log final.
- Gerenciamento de recursos: sempre usar context managers (`with`) para arquivos, conexões e transações; injete `conn`/engine para facilitar testes.
- Dependências: registre novas dependências em `pyproject.toml` e justifique mudanças em `docs/sprint-reports/`.
- Revisões: faça PRs pequenos, com descrição clara e checklist; execute `poetry run pytest -q` e linters antes de pedir revisão.
- Estilo: preserve convenções de nomes e estrutura de módulos; evite mudanças de estilo massivas em arquivos não relacionados.
- Documentação: documente decisões de design importantes e mudanças de dependência em `docs/sprint-reports/`.

### Imports & Dependencies

- Evitar imports globais de libs pesadas em módulos executados no startup da CLI; prefira imports locais dentro de funções quando apropriado.
- Organização: siga a ordem `stdlib` → `third-party` → `local` e use `isort`/config compatível com `pyproject.toml`.
- Import style: prefira imports absolutos dentro do pacote (ex.: `from src.module import X`) ou imports relativos com clareza; evite efeitos colaterais de módulo no nível superior.
- Novas dependências: registre no `pyproject.toml` e adicione justificativa em `docs/sprint-reports/`; atualize `poetry.lock` e execute a suíte de testes antes do PR.
- Dependências de desenvolvimento: declare em `[tool.poetry.dev-dependencies]` para separar runtime de dev tools (linters, test runners).
- Evite adicionar uma dependência pesada para um único uso trivial; considere alternativas mais leves ou uma implementação local pequena.
- Remoção de dependências: ao remover, faça busca global por referências, atualize testes e documente a mudança em `docs/sprint-reports/`.
- Política de atualização: atualize dependências via PR com changelog/resumo, execute `poetry run pytest -q` e verifique compatibilidade com a versão mínima de Python.
- Dependências opcionais: para funcionalidades opt-in, documente um extra em `pyproject.toml` (`extras`) ou faça import condicional com fallback claro.
- Segurança: nunca aceitar pacotes de fontes não verificadas; prefira versões com checksum e verifique CVEs para atualizações críticas.

### Development Workflow

- Branches & PRs: nomear branches como `tipo/ticket-descrição` (ex.: `feat/123-add-ingest`). Faça PRs pequenos e focados; inclua descrição, checklist e links para tarefas relacionadas.
- Pre-commit & CI: execute `pre-commit --all-files` e `poetry run pytest -q` localmente antes de abrir PR. Falhas de linter/test devem bloquear merge no CI.
- Commits: mensagens concisas com tipo/escopo (ex.: `feat(ingest): add checksum validation`); siga o padrão do time.
- Reviews: peça pelo menos uma revisão antes do merge; inclua capturas de tela ou trechos de logs para mudanças comportamentais relevantes.
- Documentação: atualize `docs/modules/` para mudanças de API ou design; adicione notas de migração quando necessário.
- Releases & Versioning: controle de versões por tag; documente mudanças breaking em release notes e `docs/sprint-reports/`.
- Migrations: qualquer alteração de schema (DB/CSV) deve incluir script de migração (`migrations/`) e testes que validem compatibilidade retroativa.
- Secrets & Config: use `.env` para dev; não commite segredos; adicione variáveis novas em `.env.example`.
- Experimental: features experimentais devem ficar em branches `exp/` e exigir validação/cleanup antes do merge em `master`.
- CI Jobs: separar jobs curtos (linters, unit tests) de jobs pesados (integration/slow); falhas críticas devem bloquear pipeline principal.
- Hotfixes: criar branches `hotfix/*` e seguir processo de revisão acelerada; documentar a razão do hotfix no PR.

### CI

- Pipeline mínimo: `poetry install` + `poetry run pytest -q` + linters.
- Pre-commit: `poetry run pre-commit run --all-files`.
- Validar checksums de snapshots; falhar pipeline se divergirem.
- Manter paridade de runtime entre CI e `pyproject.toml`; hoje o baseline
  esperado é Python 3.12.

### Critical Don't-Miss Rules

- Anti-patterns a evitar:
	- Alterar formato de CSV/snapshot sem coordenação, testes e atualização de checksums.
	- Usar singletons globais para `conn`/engine; prefira injeção de dependências.
	- `bare except:` ou silenciar exceções; sempre capture específicas e use `raise from`.
	- Fazer imports pesados no topo de módulos executáveis (CLI); importe dentro de funções.
	- Gravar em `snapshots/` ou em DB durante testes sem isolamento/rollback.

- Edge cases de dados:
	- Falta da coluna `Return`, duplicatas de data, e dados com timezone inconsistentes.
	- Dias de mercado sem negociação (zero volume) e divisões por zero em cálculos de retorno.
	- Arquivos CSV parcialmente corrompidos ou com encodings diferentes; validar parsing.

- Segurança e segredos:
	- Nunca commitar `.env` ou credenciais; use `.env.example` e variáveis de ambiente.
	- Sanitize nomes de arquivos/paths provenientes do usuário; evite injeção de shell.
	- Verificar origens de dependências e checar CVEs para upgrades críticos.

- Performance & escalabilidade:
	- Evitar carregar snapshots enormes na memória sem chunking/streaming.
	- Evitar N+1 writes ao DB — use batch inserts e transações.
	- Medir e documentar operações custosas (ETL) e fornecer versões simplificadas para testes.

- Integridade de dados:
	- Calcular e persistir `raw_checksum` antes de upserts; não mudar algoritmo de checksum sem migração/nota.
	- Validar checksums de `snapshots/` no CI; PRs que atualizam snapshots devem incluir `<file>.checksum` e justificativa.

- CI / Migrations:
	- Mudanças de schema (DB/CSV) requerem script em `migrations/`, testes de compatibilidade e notas em `docs/sprint-reports/`.
	- Pipeline deve falhar se checksums divergirem ou linters/tests falharem.

- Testes & mocks:
	- Não depender de rede em unit tests; sempre mockar `yfinance`/APIs externas.
	- Testes que alteram dados reais devem rodar somente em jobs isolados com dados de teste.

---

## Referências rápidas

- Entrypoint CLI: [src/main.py](src/main.py#L1)
- Configuração: [pyproject.toml](pyproject.toml#L1)
- Locais importantes: `src/`, `dados/`, `snapshots/`, `tests/`

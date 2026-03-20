---
project_name: 'Analise-financeira-B3'
user_name: 'Phbr'
date: '2026-03-17'
sections_completed: ['technology_stack','language_rules','framework_rules','testing','code_quality','workflow_rules','critical_rules','ux']
existing_patterns_found: 8
status: 'complete'
rule_count: 38
optimized_for_llm: true
last_updated: '2026-03-17'
---

# Contexto do Projeto para Agentes de IA

_Documento enxuto com regras críticas e padrões que agentes de IA devem seguir ao implementar código neste projeto. Conteúdo otimizado para consumo por LLMs._

---

## Tecnologias e Versões

### Resumo de Tecnologias (extraído de `pyproject.toml`)

- Python: ^3.12
- pandas: ^2.3.2
- numpy: ^2.3.2
- SQLAlchemy: ^2.0.18
- typer: ^0.24  # usar versão declarada em `pyproject.toml`
- python-dotenv: ^1.0.0
- yfinance: ^1.2.0
- pandera: ^0.29.0
- portalocker: ^3.1.0
- papermill: ^2.7.0 (opcional; habilite via `poetry install --extras "notebook"`)
- sqlparse: ^0.5.5
- Persistência: `sqlite3` (stdlib) — arquivo canônico `dados/data.db`
- Dev / CI: pytest ^7.4.0, ruff (config em `pyproject.toml`), pre-commit

## UX

- CLI: flags mínimas e mensagens esperadas estão documentadas em `docs/planning-artifacts/ux.md`. Principais flags esperadas:
  - `--ticker <TICKER>`
  - `--start_date <YYYY-MM-DD>` / `--end_date <YYYY-MM-DD>`
  - `--force-refresh`
  - `--format <text|json>` (padrão `text`)
  - `--no-network` (modo offline para testes/CI)
  - `--output <path>` (export CSV)

- Mensagens: mensagens concisas voltadas a troubleshooting (ex.: `Executando tickers ...`, `Resumo run: sucesso=<n>, falhas=<n>`, `WARN: ...`, `ERROR: ...`). Use logging estruturado para saída em CI.

- Notebooks: células de preparação devem carregar snapshots de `snapshots/` e parametrização via `ticker`, `start_date`, `end_date` — os notebooks devem gerar ao menos um plot de preços ajustados e um plot de retornos.

- Streamlit (opcional/minimal): telas para selecionar ticker/período, executar e visualizar gráfico + resumo numérico; botão `Run` deve mostrar `Processing...` e desabilitar inputs enquanto processa.

- Observação de compatibilidade: regras UX documentadas em `docs/planning-artifacts/ux.md` devem ser consideradas na implementação do CLI (`src/main.py`) e ao adicionar `--run-notebook`.

**Nota:** há uma pequena divergência de versão do `typer` entre `pyproject.toml` (0.24) e referências em `docs/project-context.md` (0.9.x). Preferir a versão declarada em `pyproject.toml` como fonte da verdade e atualizar a documentação se necessário.

## Regras Críticas de Implementação

### Regras Específicas da Linguagem (Python)

- Use `poetry` para ambiente e execução (`poetry install`, `poetry run main`).
- Evite imports pesados no startup; importe dentro de funções quando necessário.
- Siga `ruff`/`pyproject.toml` (line-length 88) e execute `pre-commit` antes de commitar.
- Nunca commitar segredos; use `.env` com `python-dotenv` para desenvolvimento local.
- Quando for implementar alguma variável de configuração, utilize `python-dotenv` e adicione a variável ao `.env.example` para referência. Nunca adicione variáveis de configuração diretamente no código ou em arquivos versionados.

### Regras Específicas de Framework

- Use `type hints` em APIs públicas e docstrings concisas para funções/módulos exportados.
- Nunca use `bare except:`; capture exceções específicas e use `raise from` para manter contexto.
- Prefira `with`/context managers para arquivos, conexões e transações.
- Funções que gravam/consultam DB devem aceitar `conn` injetado; evite singletons globais para `conn`/engine.
- Calcule e persista `raw_checksum` antes de realizar upserts no DB; não mude o algoritmo de checksum sem migração/nota.
- Em chamadas de rede/IO, favor testar via fixtures/mocks (monkeypatch/patch) em vez de rede real.
- Use `src.logging_config.get_logger` para logging estruturado; evite `print()` em produção.
- Sanitize as entradas que possam ser usadas em paths/nomes de arquivos para evitar injeção de shell/path traversal.
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

### Testes (Conciso e Acionável)

- Execute testes com `pytest` via `poetry run pytest -q`. Mantenha os testes rápidos e determinísticos.
- Organize os testes em `tests/` usando arquivos `test_*.py`; agrupe por módulo em subpastas.
- Separe testes unitários e de integração: marque testes de integração com `@pytest.mark.integration` e execute-os em um job de CI separado.
- Testes unitários não devem realizar I/O de rede. Faça mock de chamadas externas (ex.: `yfinance`) com `unittest.mock.patch`, fixtures do `pytest` ou `responses`.
- Use `sqlite3.connect(":memory:")` ou um banco em `tmp_path` para testes; injete `conn` nas funções para permitir isolamento e rollback.
- Use `tmp_path`/`tmp_path_factory` para artefatos de filesystem e garanta limpeza. Prefira fixtures para snapshots (coloque em `tests/fixtures/`).
- Valide checksums de snapshot em testes usando os helpers de `scripts/validate_snapshots.py`; testes que leem snapshots não devem escrevê-los.
- Marque testes lentos com `@pytest.mark.slow` para excluí-los da execução padrão do CI; inclua um pequeno job de smoke/integration para caminhos críticos.
- Use `monkeypatch` para controlar variáveis de ambiente e fazer patch de tempo/aleatoriedade para testes determinísticos.
- Busque alta cobertura nos módulos centrais de ETL/adapter/persistência; adicione testes de integração focados que rodem em modo `--no-network`.
- CI: execute `poetry run pre-commit --all-files` e `poetry run pytest -q` como passos mínimos do pipeline; faça o CI falhar em caso de checksum/lint/testes com falha.


### Qualidade de Código e Estilo

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

### Importações e Dependências

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

### Fluxo de Trabalho de Desenvolvimento

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

### Integração Contínua (CI)

- Pipeline mínimo: `poetry install` + `poetry run pytest -q` + linters.
- Pre-commit: `poetry run pre-commit run --all-files`.
- Validar checksums de snapshots; falhar pipeline se divergirem.
- Manter paridade de runtime entre CI e `pyproject.toml`; hoje o baseline
  esperado é Python 3.12.

### Regras Críticas — Não Ignorar

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

## Diretrizes de Uso

**Para Agentes de IA:**

- Leia este arquivo antes de implementar qualquer código.
- Siga todas as regras conforme documentado; em caso de dúvida, prefira a opção mais restritiva.
- Se uma mudança afetar múltiplas regras (por exemplo, atualização de dependência), atualize este arquivo e adicione uma justificativa curta em `docs/sprint-reports/`.
- Mantenha saídas determinísticas: faça mock das chamadas de rede nos testes e utilize o modo `--no-network` para execuções de smoke em CI.

**Para Humanos / Mantenedores:**

- Mantenha este arquivo enxuto e focado nas necessidades dos agentes; evite conteúdo tutorial.
- Atualize quando o stack de tecnologia mudar (editar `pyproject.toml` primeiro) e atualize `last_updated`.
- Revise trimestralmente para remover regras desatualizadas ou óbvias.
- Ao alterar o esquema de snapshot ou o algoritmo de checksum, adicione scripts de migração em `migrations/` e atualize os testes.

Última Atualização: 2026-03-17

---

## Referências rápidas

- Entrypoint CLI: [src/main.py](src/main.py#L1)
- Configuração: [pyproject.toml](pyproject.toml#L1)
- Locais importantes: `src/`, `dados/`, `snapshots/`, `tests/`

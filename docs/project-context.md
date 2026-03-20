---
project_name: 'Analise-financeira-B3'
user_name: 'Phbr'
date: '2026-03-20'
sections_completed: ['technology_stack','language_rules','framework_rules','testing','code_quality','workflow_rules','critical_rules','ux']
existing_patterns_found: 8
status: 'complete'
rule_count: 38
optimized_for_llm: true
last_updated: '2026-03-20'
updated_by_workflow: 'generate-project-context'
---

# Contexto do Projeto para Agentes de IA

_Documento enxuto com regras críticas e padrões que agentes de IA devem seguir ao implementar código neste projeto. Conteúdo otimizado para consumo por LLMs._

---

## Tecnologias e Versões

### Resumo conciso (fonte: `pyproject.toml`)

- Python: ^3.12
- CLI: `typer` ^0.24
- Persistência: `sqlite3` (stdlib); SQLAlchemy ^2.0.18
- Dados: `pandas` ^2.3.2, `numpy` ^2.3.2
- Adapter financeiro: `yfinance` ^1.2.0
- Validação: `pandera` ^0.29.0
- I/O / locking: `portalocker` ^3.1.0
- Utilitários SQL: `sqlparse` ^0.5.5
- Notebooks (opcional): `papermill` ^2.7.0, `ipykernel` ^7.2.0

**Dev / CI**

- Testes: `pytest` ^7.4.0
- Lint: `ruff` ^0.14.14 (line-length = 88)
- Hooks: `pre-commit` ^3.3.0

Observações:

- Preferir as versões declaradas em `pyproject.toml` como fonte da verdade.
- Extras opcionais (`notebook`) gerenciados via `poetry extras`.
- O CI assume paridade de runtime com Python 3.12.

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

## UX — Rascunho enxuto

- CLI: mantenha `src/main.py` simples; flags principais: `--ticker`, `--start_date`, `--end_date`, `--force-refresh`, `--format <text|json>`, `--no-network`, `--output <path>`.
- Mensagens: prefira mensagens concisas e acionáveis; use logging estruturado para saídas de CI e `--format json` para saídas estruturadas em automação.
- Startup: evite carregamento pesado no startup da CLI; carregue dados/recursos apenas quando necessários.
- Notebooks: usar snapshots de `snapshots/`, parametrização por `ticker`/`start_date`/`end_date`, produzir pelo menos um gráfico de preços ajustados e um gráfico de retornos; inclua célula de preparação que valida checksums.
- Streamlit (opcional): componentes mínimos — seleção de ticker/período, botão `Run`, estado `Processing...`, visualização de gráfico e resumo numérico; evite lógica pesada no UI, delegue ao backend/ETL.
- Acessibilidade/UX leve: mensagens de erro e estados intermediários claros; botões desabilitados durante processamento; tempos limite configuráveis para chamadas de rede.
- Compatibilidade: preferir versões em `pyproject.toml` como fonte da verdade; documentar divergências em `docs/sprint-reports/`.

## Regras Críticas de Implementação
### Regras Específicas da Linguagem (Python) — Rascunho enxuto

- Ambiente: use `poetry` para instalar e executar (`poetry install`, `poetry run main`).
- Imports: evite imports pesados no nível de módulo (CLI/entrypoint); importe localmente dentro de funções para reduzir tempo de startup e dependências carregadas em testes.
- Lint/format: respeite `ruff` (line-length = 88) e execute `pre-commit` antes de PRs.
- Segredos/config: não commitar `.env`; use `python-dotenv` para dev e mantenha `.env.example` atualizado.
- Tipagem: adicione `type hints` em APIs públicas e para funções que serão reusadas por agentes/consumers.
- Erros: não usar `bare except:`; capture exceções específicas e use `raise from` para preservar contexto.
- Recursos: use `with`/context managers para arquivos, transações e conexões; funções que manipulam DB devem aceitar `conn` injetado.
- Idempotência: calcule e persista `raw_checksum` antes de upserts; preserve algoritmo de checksum ou documente migração.
- Logging: use `src.logging_config.get_logger` para logs estruturados; evite `print()` em produção.
- Segurança: sanitize nomes de arquivos/paths fornecidos pelo usuário para evitar path traversal/injeção.
- Testes: unit tests não devem acessar rede; mocke `yfinance`/IO e prefira `sqlite3.connect(":memory:")` ou `tmp_path` para isolamento.
- Adapter contract: obtenha adapters via `src.adapters.factory.get_adapter()`; não introduza rotas alternativas de criação sem atualizar `docs/modules/adapter-guidelines.md`.

### Regras Específicas de Framework — Rascunho enxuto

- Adapter Factory: sempre usar `src.adapters.factory.get_adapter()` / `register_adapter()`; adapters devem implementar a interface documentada em `docs/modules/adapter-guidelines.md` e ser testáveis via fixtures.
- ETL: funções em `src/etl/` aceitam `conn` injetado, retornam DataFrame(s) padronizados e não fazem efeitos colaterais fora de transação controlada.
- CLI: `src/main.py` (typer) deve manter comandos leves; imports pesados apenas dentro da função do comando; exposing `--no-network` para execuções de teste/CI.
- DB: evitar singletons globais; usar `with conn:` para transações; preferir injeção explícita de engine/sessão e documentar usos de SQLAlchemy.
- Migrations: alterações de schema devem incluir script em `migrations/` e testes de compatibilidade; atualizar `docs/sprint-reports/`.
- Adapters de rede: aplicar retry/backoff e timeouts configuráveis; mockar em testes e não depender de rede em unit tests.
- Caching / snapshots: gravar snapshots em `snapshots/` com checksum; leituras validadas em CI; não sobrescrever sem atualização de checksum.
- Streams/Batch: evitar carregar grandes snapshots em memória sem chunking; oferecer modo streaming para ETL pesado.
- Testes de framework: ter fixtures para adapters, `tmp_db` e `tmp_path`; marcar integração com `@pytest.mark.integration`.
- Proibições: não adicionar servidor web (Flask/FastAPI) sem justificativa documentada; não criar caminhos alternativos de inicialização que burlem `get_adapter`.
- Observabilidade: usar `src.logging_config` e emitir eventos estruturados em pontos críticos do ETL/adapter/persistência.

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

### Testes — Rascunho enxuto

- Execução: rode testes com `poetry run pytest -q`; CI mínimo: `pre-commit --all-files` + `poetry run pytest -q`.
- Separação: mantenha testes unitários (fast) separados de integração (marcados com `@pytest.mark.integration`) e execute integração em job separado.
- Rede: testes unitários NÃO devem acessar rede; use `monkeypatch`/`unittest.mock` ou fixtures para mockar `yfinance` e outras chamadas externas. Use `NETWORK_MODE` (playback/record) para fixtures que fazem playback.
- DB/isolamento: use `sqlite3.connect(":memory:")` ou DB temporário (`tmp_path`) e injete `conn` nas funções; use fixtures autouse para isolar `db.connect`/metadata quando necessário.
- Snapshots: leia snapshots de `snapshots/` via fixtures; valide checksums SHA-256 com `scripts/validate_snapshots.py` em CI; não sobrescrever snapshots sem atualizar `<file>.checksum` e justificar no PR.
- Fixtures padrão: forneça `yf_mock`, `tmp_db`/`sample_db`, `snapshot_dir`, `mock_metadata_db` e outros helpers em `tests/conftest.py` para reduzir duplicação.
- Determinismo: controle tempo/aleatoriedade via `monkeypatch`; prefira dados de fixtures (`tests/fixtures`) para playback.
- Marcações: marque testes lentos com `@pytest.mark.slow` e testes de integração com `@pytest.mark.integration`.
- Cobertura focalizada: priorize cobertura nas camadas de ETL/adapters/persistência; mantenha testes rápidos e confiáveis.
- CI extras: falhar pipeline em divergência de checksums, lint ou testes; permitir `--no-network` em jobs de smoke.


### Qualidade de Código e Estilo — Rascunho enxuto

- Lint & format: siga `pyproject.toml` (`ruff`, `line-length=88`) e execute `pre-commit --all-files` antes de PRs.
- Tipagem & docs: use `type hints` em APIs públicas e docstrings concisas para funções/módulos exportados.
- Funções: prefira funções pequenas e puras; evite efeitos colaterais e aninhamento profundo.
- Exceções: capture exceções específicas; evite `bare except:` e use `raise from`.
- Logging: use `src.logging_config.get_logger` para logs estruturados; não usar `print()` em produção.

Exemplo mínimo:

```python
from src.logging_config import get_logger
logger = get_logger(__name__)
logger.info("iniciando processamento", extra={"ticker": "PETR4"})
```

- Recursos: use context managers (`with`) para arquivos/conexões; injete `conn`/engine para testes.
- Dependências: registre novas dependências em `pyproject.toml`, atualize `poetry.lock` e justifique em `docs/sprint-reports/`.
- PRs: mantenha PRs pequenos, execute linters/tests localmente antes de pedir revisão.
- Documentação: documente decisões de design importantes em `docs/modules/` ou `docs/sprint-reports/`.

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

### Fluxo de Trabalho de Desenvolvimento — Rascunho enxuto

- Branches: nomeie branches `tipo/ticket-descrição` (ex.: `feat/123-add-ingest`) e mantenha PRs pequenos e focados.
- Commits: mensagens concisas com `tipo(escopo): descrição` (ex.: `fix(ingest): handle empty snapshots`).
- PRs e reviews: executar `pre-commit --all-files` + linters/tests localmente; peça pelo menos uma revisão antes de merge.
- Migrations: mudanças de schema exigem script em `migrations/`, testes e notas de migração em `docs/sprint-reports/`.
- Dependências: adicione/justifique dependências em `pyproject.toml` e atualize `poetry.lock` em PRs.
- Feature flags/experimental: coloque experimentos em `exp/*` e documente cleanup antes do merge em `master`.
- Hotfixes: use branches `hotfix/*` com revisão acelerada e descrição clara do problema resolvido.
- CI: separar jobs rápidos (lint/unit) de jobs pesados (integration/slow); falhas críticas bloqueiam merge.
- Secrets: não commitar segredos; use `.env.example` e variáveis de ambiente; adicione scanners em pre-commit/CI.
- Checklist padrão: inclua itens mínimos no PR (linters pass, testes locais, changelog/justificativa, atualizações de docs quando aplicável).

### Integração Contínua (CI)

- Pipeline mínimo: `poetry install` + `poetry run pytest -q` + linters.
- Pre-commit: `poetry run pre-commit run --all-files`.
- Validar checksums de snapshots; falhar pipeline se divergirem.
- Manter paridade de runtime entre CI e `pyproject.toml`; hoje o baseline
  esperado é Python 3.12.

### Regras Críticas — Não Ignorar

**Resumo crítico (Rascunho enxuto)**

- Anti-patterns a evitar: alterar formato de CSV/snapshot sem coordenação; usar singletons globais para `conn`/engine; `bare except:`; imports pesados no startup; gravar em `snapshots/` ou DB durante testes sem isolamento.
- Dados: trate ausência da coluna `Return`, duplicatas de datas e timezones inconsistentes; prevenir divisões por zero e validar encodings/parsings de CSV.
- Segurança: nunca commitar `.env`/segredos; use `.env.example`; sanitize paths; verifique CVEs antes de upgrades críticos.
- Performance: evite carregar snapshots enormes em memória (use chunking/streaming); evite N+1 writes (batch + transações).
- Integridade: calcule e persista `raw_checksum` antes de upserts; atualize `<file>.checksum` e justifique PRs que mudem snapshots.
- CI & Migrations: mudanças de schema requerem `migrations/`, testes de compatibilidade e notas em `docs/sprint-reports/`; CI deve falhar em divergência de checksum/lint/testes.
- Testes: não depender de rede em unit tests; marcar e isolar testes que alterem dados reais; forneça fixtures de playback/seed (`yf_mock`, `sample_db`, `snapshot_dir`).

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

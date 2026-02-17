# Story 4.1: Implementar CLI de métricas e health

Status: ready-for-dev

## Story

Como Operador/Administrador (CLI),
eu quero comandos operacionais de métricas e health (`--metrics`, `--test-conn`, `--health`),
para que eu possa checar conectividade, integridade e métricas operacionais do sistema localmente e em pipelines de CI.

## Acceptance Criteria

1. `poetry run main --metrics` exibe métricas operacionais básicas (jobs por ticker, latência média, taxa de erro por fonte, rows_fetched) em JSON e retorna exit-code 0.
2. `poetry run main --test-conn --provider <name>` executa um teste de conexão ao adaptador nomeado, com timeouts configuráveis, e reporta success/failure com detalhes (latência, erro recebido) em ≤ 5s em condições normais.
3. `poetry run main --health` retorna um resumo compactado de integridade (DB acessível, últimos snapshot presente, filas/locks por ticker) e um exit-code apropriado (0 healthy, !=0 unhealthy).
4. Implementação reutiliza a infra de logging e DB já existente (`dados/data.db`) e não adiciona dependências pesadas desnecessárias.
5. Testes unitários cobrem handlers de CLI, mocks para adaptadores e critérios de aceitação descritos; integração leve (mocked) valida `--metrics` output JSON e `--test-conn` behavior.
6. Documentação do comando atualizada em `README.md` e `docs/playbooks/quickstart-ticker.md` com exemplos de uso.

## Tasks / Subtasks

- [ ] Task 1: API e CLI
  - [ ] Criar subcomando `metrics` e flags `--metrics`, `--test-conn`, `--health` usando Typer (suggested: `src/cli/metrics.py` ou `src/main.py` subcommand)
  - [ ] Reusar `src.dados_b3` / `src.retorno` e contratos DB (`db.read_prices`/`db.*`) quando necessário
- [ ] Task 2: Implementação das métricas
  - [ ] Implementar coletor leve de métricas internas (jobs_count, avg_latency_ms, error_rate, rows_fetched)
  - [ ] Exportar JSON via stdout e opcional `.metrics` file quando flag `--output` for fornecida
- [ ] Task 3: Health & Test-Conn
  - [ ] Implementar `--test-conn --provider` que chama adaptador em modo dry-run com timeout e reporta latência/erro
  - [ ] Implementar `--health` que valida: conexão com DB, existência recente de snapshots, integridade básica do schema
- [ ] Task 4: Tests
  - [ ] Unit tests pytest com monkeypatch para adaptadores e DB (mocks), cobertura dos handlers CLI
  - [ ] Integration test mocked que valida saída JSON de `--metrics` e comportamento `--test-conn`
- [ ] Task 5: Docs e exemplos
  - [ ] Atualizar `README` quickstart com exemplos de comandos
  - [ ] Adicionar snippet em `docs/playbooks/quickstart-ticker.md`

## Dev Notes

- Linguagens / libs recomendadas: Python (3.14+), Typer para CLI, `pandas`/`sqlalchemy` já no projeto; evite adicionar dependências pesadas. Se for necessário, prefira `prometheus_client` apenas se houver justificativa (caso contrário, serializar JSON simples é suficiente).
- Arquitetura: adicionar `src/cli/metrics.py` com função `register_metrics_cli(app: Typer)` e handler que reutiliza funções de data/DB existentes. Mantenha side-effect mínimo em código de coleta (opções `--dry-run` / `--timeout`).
- File layout sugerido:
  - `src/cli/metrics.py` — subcommands Typer (`metrics`, `test-conn`, `health`)
  - `src/metrics/collector.py` — funções puras para coletar e agregar métricas
  - `src/ops/health.py` — checks de DB e snapshots
  - Tests: `tests/test_cli_metrics.py`, `tests/test_health.py` (mock DB/adapters)
- Logging e output:
  - Use JSON-structured logs para métricas e health summaries
  - `--metrics` deve poder receber `--output <path>` para gravar arquivo JSON para CI
- Timeouts e configuração:
  - Ler `METRICS_TIMEOUT_SECONDS` e `TEST_CONN_TIMEOUT_SECONDS` de env (com `.env.example` já presente)
  - Respeitar `LOG_LEVEL` e usar `logger = logging.getLogger(__name__)` com JSON formatting (recomendar `python-json-logger` se aceitável)
- Permissões e segurança:
  - Nenhum segredo deve ser gravado; conexões de teste devem usar modo read-only quando possível

### Project Structure Notes

- Alinhar nomes de módulo com convenções do projeto (snake_case), evite introduzir novos top-level packages sem necessidade.
- Siga padrões de testes existentes (pytest fixtures em `tests/conftest.py`, uso de `tests/fixtures/sample_ticker.csv`).

### References

- Source: docs/planning-artifacts/epics.md#Epic-4 — requisitos operacionais e métricas
- Sprint status: docs/implementation-artifacts/sprint-status.yaml

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Completion Notes List

- Arquivo criado por workflow `create-story` versão local

### File List

- docs/implementation-artifacts/4-1-implementar-cli-de-metricas-e-health.md

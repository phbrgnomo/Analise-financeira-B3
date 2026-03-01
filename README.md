# Análise Financeira — B3

[![CI](https://github.com/phbrgnomo/Analise-financeira-B3/actions/workflows/ci.yml/badge.svg)](https://github.com/phbrgnomo/Analise-financeira-B3/actions/workflows/ci.yml) [![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)

Uma ferramenta leve para coletar dados de mercados (B3), calcular retornos e métricas de risco, e gerar relatórios simples a partir de séries históricas.

**Status:** Projeto experimental / utilitários para análise local

> Visão rápida: coleta dados via adapter factory (`src/adapters/factory.py`), calcula retornos e estatísticas em `src/retorno.py` e tem entrypoint em `src/main.py`.

## Recursos principais
- Coleta de cotações OHLC/Adj Close para ativos B3 (sufixo `.SA`).
- Cálculo de retornos diários e métricas de risco (volatilidade, conversões anuais).
- Estrutura para persistir séries em CSV em `dados/` e snapshots em `snapshots/`.
- Scripts de exemplo e fixtures para testes em `tests/`.

## Pré-requisitos
- Python 3.12+ (recomendado)
- poetry (para gerenciar ambiente e dependências)

## Configuração (variáveis de ambiente)

Algumas configurações podem ser alteradas via variáveis de ambiente. Um
exemplo está em `.env.example` — copie para `.env` e ajuste conforme
necessário.

- **SNAPSHOT_TTL**: tempo em segundos que um cache de snapshot é considerado
  válido. Padrão `86400` (um dia). Use com o comando `ingest-snapshot`.
- **SNAPSHOT_CACHE_FILE**: caminho para o arquivo JSON onde o cache é
  armazenado. Valor padrão `dados/snapshot_cache.json`.
- **SNAPSHOTS_KEEP_LATEST**: quantidade de snapshots recentes por ticker a
  manter no diretório de snapshots. Padrão `1`.
- **DEFAULT_TICKERS**: tickers padrão usados no `main run` quando `--ticker`
  não é informado. Exemplo: `PETR4,ITUB3,BBDC4`.

- **VALIDATION_INVALID_PERCENT_THRESHOLD**: limite percentual usado pelo
  processo de validação para considerar uma operação como inválida. Valor
  padrão: `0.1` (10%). Deve ser um número decimal entre `0` e `1` (por
  exemplo `0.05` para 5%). Para sobrescrever localmente, adicione em
  `.env`:

```
VALIDATION_INVALID_PERCENT_THRESHOLD=0.05
```

  Isso permite reduzir ou aumentar a sensibilidade da validação conforme o
  contexto (ex.: aceitar até 5% de linhas inválidas antes de tratar como
  falha).

- **INGEST_LOCK_TIMEOUT_SECONDS**: tempo máximo em segundos que uma chamada
  de ingest aguardará para obter um bloqueio por ticker. Padrão `120`.

- **INGEST_LOCK_MODE**: define como reagir quando outro processo já detém o
  bloqueio para o mesmo ticker. `wait` (padrão) faz o comando aguardar até
  que o recurso seja liberado; `exit` faz com que a chamada falhe imediatamente
  com mensagem de erro clara.

- **LOCK_DIR**: diretório onde os arquivos de bloqueio por ticker são
  armazenados. O valor padrão é `locks/` (no diretório de trabalho atual) e
  é criado automaticamente. Ajustar esta variável permite colocar locks em
  um caminho específico quando múltiplos executores compartilham o mesmo
  ambiente de trabalho.

  Exemplo em `.env`:

  ```bash
  INGEST_LOCK_MODE=exit
  INGEST_LOCK_TIMEOUT_SECONDS=30
  ```

## Quickstart

1. Instale dependências (com `poetry`):

```bash
poetry install
```

2. Execute o fluxo principal da aplicação (entrypoint):

```bash
poetry run main run
# ticker específico (padrão B3)
poetry run main run --ticker PETR4
```

3. Exemplos e testes rápidos:

```bash
poetry run pytest -q
./examples/run_quickstart_example.sh
```

### Modo de testes de rede (NETWORK_MODE)

Para reduzir flakiness em CI, os testes que dependem de chamadas de rede rodam
por padrão em modo `playback`, usando fixtures determinísticas.

- Execução local (playback, padrão):

```bash
poetry run pytest
```

- Atualizar gravações/usar rede (modo `record`) — execute apenas em ambiente controlado:

```bash
NETWORK_MODE=record poetry run pytest tests/adapters/test_adapters.py::TestYFinanceAdapter::test_fetch
```

As instruções completas e o playbook estão em `docs/playbooks/testing-network-fixtures.md`.

## Uso e convenções
- Dados são obtidos através da fábrica de adaptadores (`src.adapters.factory`). O adaptador padrão é `yfinance`, mas outros podem ser registrados. Para fins de testes e *smoke* CLI há também um provedor `dummy` embutido; ele gera um DataFrame pequeno sem acesso à rede e pode ser usado via `get_adapter("dummy")` ou pelo parâmetro `--provider dummy` na CLI.

  Exemplo de uso:
  ```python
  from src.adapters.factory import get_adapter

  adapter = get_adapter("yfinance")  # ou outro provider registrado
  df = adapter.fetch("PETR4.SA", start_date="2022-01-01", end_date="2022-12-31")
  print(df.head())
  ```
- Na CLI, informe tickers no padrão B3 sem sufixo de provider (ex.: `PETR4`, `MGLU3`, `BOVA11`).
- A adaptação para formato de provider (ex.: `.SA`) é feita internamente pelo adapter.
- Dados persistidos ficam em `dados/data.db` no banco SQLite.
- No banco (`prices` e `returns`), os tickers são persistidos no padrão B3 (ex.: `PETR4`).
- A coluna `date` nas tabelas canônicas usa afinidade `DATE`.
- Cálculos anuais usam 252 dias úteis por convenção do projeto.
- O pipeline agora suporta ingestão de snapshots via CLI usando `ingest-snapshot`.
  Esta rotina aplica cache com TTL e faz ingestão incremental no banco, evitando
  reprocessamento quando o arquivo não mudou. Veja abaixo para detalhes de
  flags.
  Use este comando apenas quando você já tiver um CSV local para importar.

### Comandos principais da CLI

- Executar ETL padrão (ingestão + retornos):

```bash
poetry run main run
```

- Executar ETL para um ticker:

```bash
poetry run main run --ticker PETR4
```

- Calcular retornos para ticker específico:

```bash
poetry run main compute-returns --ticker PETR4
```

- Calcular retornos para todos os tickers existentes no banco:

```bash
poetry run main compute-returns
```

- Ingerir CSV local no banco (incremental + cache/checksum):

```bash
poetry run main ingest-snapshot snapshots/PETR4_snapshot.csv --ticker PETR4
```

- Exportar dados do SQLite para CSV:

```bash
poetry run main export-csv --ticker PETR4
```

## Estrutura do repositório (resumo)
- `src/` — código principal
  - `src/main.py` — entrypoint do CLI (usa `src.adapters.factory` para selecionar provedores)
  - `src/ingest/` — orquestração de ingestão, snapshots e persistência incremental
  - `src/retorno.py` — cálculos de retorno/risco
- `dados/` — CSVs de séries históricas e outputs gerados
- `snapshots/` — snapshots e checksums para validação
- `tests/` — testes unitários e fixtures
- `docs/` — documentação e playbooks do projeto

## Desenvolvimento

- Formatação e lint:

```bash
# Usar ruff conforme configuração do projeto
poetry run ruff check src tests
```

- Executar testes:

```bash
poetry run pytest
```

## Arquivos úteis
- Exemplos e playbooks: `docs/playbooks/` e `examples/`
- Scripts úteis: `scripts/install-hooks.sh`, `examples/run_quickstart_example.sh`

## Exemplo: Checksums

Há um exemplo prático que demonstra o uso de `src.utils.checksums`:

- Arquivo: [examples/checksums_example.py](examples/checksums_example.py)
- Teste associado: [tests/test_checksums.py](tests/test_checksums.py)

Como usar:

```bash
python examples/checksums_example.py
```

O script calcula o SHA256 do arquivo de exemplo `snapshots/PETR4_snapshot_test.csv` e grava um arquivo `*.checksum` ao lado do CSV.

## Onde ler mais
- Documentação e planejamento do projeto em `docs/`.
- Para entender o fluxo de ingestão e esquema canônico, veja [docs/implementation-artifacts/1-11-definir-esquema-canonico-de-dados-e-documentacao-do-modelo-schema-examples.md](docs/implementation-artifacts/1-11-definir-esquema-canonico-de-dados-e-documentacao-do-modelo-schema-examples.md).

- Guia de implementação de adaptadores: [docs/modules/adapter-guidelines.md](docs/modules/adapter-guidelines.md)
- Checklist de PR para adaptadores: [docs/modules/adapter-pr-checklist.md](docs/modules/adapter-pr-checklist.md)

## Notas operacionais — arquivos raw e metadados

- Arquivos CSV raw são gravados em `raw/<provider>/` com o padrão `<ticker>-YYYYMMDDTHHMMSSZ.csv`.
- Um checksum SHA256 é gerado e gravado ao lado de cada CSV como `*.checksum`.
- Metadados de ingestão são persistidos em `metadata/ingest_logs.jsonl` (JSON Lines, append-only).
- Recomenda-se proteger artefatos sensíveis com permissões apenas do dono (owner-only). Para aplicar localmente:

```bash
# tornar arquivos de metadados e raw inacessíveis a outros usuários
chmod -R 600 metadata dados/raw
```

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

## Quickstart

1. Instale dependências (com `poetry`):

```bash
poetry install
```

2. Execute a aplicação (entrypoint):

```bash
poetry run main
# ou alternativamente
python -m src.main
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
- Ao coletar ativos da B3 via Yahoo, adicione o sufixo `.SA` (ex.: `PETR4.SA`).
- Dados persistidos ficam na pasta `dados/` em CSV com coluna `Return` para retornos diários.
- Cálculos anuais usam 252 dias úteis por convenção do projeto.
- O pipeline agora suporta ingestão de snapshots via CLI usando `ingest-snapshot`.
  Esta rotina aplica cache com TTL e faz ingestão incremental no banco, evitando
  reprocessamento quando o arquivo não mudou. Veja abaixo para detalhes de
  flags.

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

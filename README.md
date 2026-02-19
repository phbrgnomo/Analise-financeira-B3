# Análise Financeira — B3

[![CI](https://github.com/phbrgnomo/Analise-financeira-B3/actions/workflows/ci.yml/badge.svg)](https://github.com/phbrgnomo/Analise-financeira-B3/actions/workflows/ci.yml) [![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)

Ferramenta leve para coletar dados de mercados (B3), calcular retornos e métricas de risco, e gerar relatórios simples a partir de séries históricas.

**Status:** Projeto experimental / utilitários para análise local

> Visão rápida: coleta dados via Yahoo Finance (adaptador em `src/dados_b3.py`), calcula retornos e estatísticas em `src/retorno.py` e tem um entrypoint em `src/main.py`.

## Recursos principais
- Coleta de cotações OHLC/Adj Close para ativos B3 (sufixo `.SA`).
- Cálculo de retornos diários e métricas de risco (volatilidade, conversões anuais).
- Estrutura para persistir séries em CSV em `dados/` e snapshots em `snapshots/`.
- Scripts de exemplo e fixtures para testes em `tests/`.

## Pré-requisitos
- Python 3.12+ (recomendado)
- poetry (para gerenciar ambiente e dependências)

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

## Uso e convenções
- Ao coletar ativos da B3 via Yahoo, adicione o sufixo `.SA` (ex.: `PETR4.SA`).
- Dados persistidos ficam na pasta `dados/` em CSV com coluna `Return` para retornos diários.
- Cálculos anuais usam 252 dias úteis por convenção do projeto.

## Estrutura do repositório (resumo)
- `src/` — código principal
  - `src/main.py` — entrypoint do CLI
  - `src/dados_b3.py` — adaptador / ingestão de preços
  - `src/retorno.py` — cálculos de retorno/risco
- `dados/` — CSVs de séries históricas e outputs gerados
- `snapshots/` — snapshots e checksums para validação
- `tests/` — testes unitários e fixtures
- `docs/` — documentação e playbooks do projeto

## Desenvolvimento

- Formatação e lint:

```bash
# Usar ruff e black conforme configuração do projeto
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

---

Se você quiser, eu posso: gerar badges adicionais (coverage, PyPI quando aplicável), adicionar exemplos de uso com parâmetros do `src.main`, ou abrir um PR com pré-commit configurado. Qual próximo passo prefere?

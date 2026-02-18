## Análise de dados da B3

Este projeto visa utilizar dados da B3 para análise financeira

Esse projeto tem a finalidade apenas de aprendizado. Use pelo seu próprio risco.

<!-- CI badge -->
![CI](https://github.com/phbrgnomo/Analise-financeira-B3/actions/workflows/ci.yml/badge.svg)

## Plano de implementação

- `[]`Coleta de preços
- `[]`Cálculo de retorno, variancia, risco(volatilidade), e outras estatísticas
- `[]`Cálculo de correlação entre diferentes ativos
- `[]`Cálculo de Carteira eficiente usando Teoria de Markovitz
- `[]`Cáclulo de carteira utilizando CAPM
- `[]`Modelo Black-Litterman

## Possíveis implementações futuras
- `[]`Adicionar mercados de criptos

## Configuração local (env)

Para configurar variáveis de ambiente locais, copie o arquivo de exemplo:

```
cp .env.example .env
```

Preencha os valores em `.env`. Variáveis importantes:
- `YF_API_KEY` (opcional) — chave para provedores quando necessário
- `DATA_DIR` — diretório de dados local (padrão `./dados`)
- `SNAPSHOT_DIR` — onde snapshots CSV são gravados (padrão `./snapshots`)
- `LOG_LEVEL` — `INFO` por padrão

Nunca comite seu arquivo `.env` com segredos reais.

## Quickstart

Instalação (recomenda-se usar `poetry`):

```bash
poetry install
```

Executar a CLI de ajuda:

```bash
poetry run main --help
# ou, sem poetry (ambiente já configurado):
python -m src.main --help
```

Rodar testes:

```bash
poetry run pytest -q
```

- CI Quick Reference

- O workflow CI roda em pull requests para qualquer branch, e em pushes apenas nas branches protegidas `main`/`master`.
- Jobs principais: `lint`, `test`, `smoke`.
- `test` executa `poetry install` e `pytest` gerando `reports/junit.xml`.
- `smoke` executa uma instalação rápida (`poetry install --no-dev`) e roda `tests/ci/smoke.sh`.
- Em caso de falha o CI faz upload dos artifacts (relatórios e logs) para auxiliar debugging.

Para mais detalhes, veja `.github/workflows/ci.yml` e `tests/ci/README.md`.

Habilitar `pre-commit` hooks (já configurado no projeto):

```bash
poetry run pre-commit install
poetry run pre-commit run --all-files
```

Local de dados e snapshots:

- `dados/` — CSVs por ativo (gerados por `src.main`)
- `snapshots/` — snapshots gerados pela pipeline

Documentação adicional no diretório `docs/`.

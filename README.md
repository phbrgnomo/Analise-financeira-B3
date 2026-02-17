## Análise de dados da B3

Este projeto visa utilizar dados da B3 para análise financeira

Esse projeto tem a finalidade apenas de aprendizado. Use pelo seu próprio risco.

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

Instalação (usando `poetry`):

```bash
poetry install
```

Executar CLI help:

```bash
poetry run main --help
# ou
python -m src.main --help
```

Rodar testes:

```bash
pytest -q
```
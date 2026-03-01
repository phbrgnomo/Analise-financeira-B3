# Quickstart CLI

Este documento descreve os passos mínimos para instalar o projeto e usar a CLI atual.

Pré-requisitos
- Python 3.12 (virtualenv/poetry recomendado)
- `poetry` instalado (opcional) ou use `pip` conforme `pyproject.toml`

Instalação

1. Clonar o repositório

```bash
git clone https://github.com/phbrgnomo/Analise-financeira-B3.git
cd Analise-financeira-B3
```

2. Instalar dependências (modo dev):

```bash
poetry install
# ou, sem poetry:
# python -m venv .venv
# source .venv/bin/activate
# pip install -r requirements-dev.txt
```

Uso básico

Executar fluxo principal ETL (ingestão + cálculo de retornos):

```bash
poetry run main run
```

Executar para ticker específico (padrão B3):

```bash
poetry run main run --ticker PETR4
```

Executar ingestão pontual via subcomando `pipeline ingest`:

```bash
poetry run main pipeline ingest PETR4 --force-refresh
# ou com provider explícito
poetry run main pipeline ingest --source yfinance PETR4 --force-refresh
```

Calcular retornos:

```bash
# ticker específico
poetry run main compute-returns --ticker PETR4

# todos os tickers existentes no banco
poetry run main compute-returns
```

Exemplos rápidos

- Importar CSV local para o banco com ingestão incremental (caso você já
  tenha um arquivo de dados e queira carregá-lo):

 ```bash
 poetry run main ingest-snapshot snapshots/PETR4_snapshot.csv --ticker PETR4
 ```

O comando também calcula checksum e evita reprocessar arquivos idênticos.

- Exportar dados para CSV:

```bash
poetry run main export-csv --ticker PETR4
```

Verificação de snapshots

- Verifique localmente:

```bash
ls -l snapshots/
sha256sum snapshots/PETR4_snapshot.csv
```

Notas

- Alinhe a versão do Python com `pyproject.toml` antes de executar (`python = "^3.12"`).
- Se a CLI mudar flags/semântica, atualize este quickstart e o README.

Checklist mínimo após seguir o quickstart

- [ ] ETL executado com `main run`
- [ ] Dados persistidos em `dados/data.db`
- [ ] Export CSV gerado com `main export-csv`

Referências
- Contrato de metadados: `docs/schema.md`
- Playbook: `docs/playbooks/quickstart-ticker.md` (fluxo completo)

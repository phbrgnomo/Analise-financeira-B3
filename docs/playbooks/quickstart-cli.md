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

Observação sobre feedback visual

- Os comandos principais da CLI exibem progresso por etapa, duração e resumo
  final por padrão.
- O identificador `job_id=...` continua sendo emitido nos fluxos de ingestão
  para manter compatibilidade com automações e troubleshooting.

Executar fluxo principal ETL (ingestão + cálculo de retornos):

```bash
poetry run main run
```

Executar para ticker específico (padrão B3):

```bash
poetry run main run --ticker PETR4
```

Saída esperada, em alto nível:

```text
▶ run: executando ticker=PETR4 com provider=yfinance
→ [1/1] PETR4
… ingestão — ticker=PETR4 | force_refresh=False
… cálculo de retornos — PETR4
■ Resumo run: sucesso=1, falhas=0 (1.23s)
```

Executar ingestão pontual via subcomando `pipeline ingest`:

```bash
poetry run main pipeline ingest PETR4 --force-refresh
# ou com provider explícito
poetry run main pipeline ingest --source yfinance PETR4 --force-refresh
```

Esse comando também exibe duração e o motivo do processamento quando
disponível, por exemplo `reason: checksum_match` ou `reason: forced_refresh`.

Gerar amostra visual (raw + canônico) via adapter, sem persistir no DB:

```bash
poetry run main pipeline pull-sample PETR4
# provider explícito e janela customizada
poetry run main pipeline pull-sample --source yfinance PETR4 --days 7
```

Calcular retornos:

```bash
# ticker específico
poetry run main compute-returns --ticker PETR4

# todos os tickers existentes no banco
poetry run main compute-returns
```

O comando informa ticker atual, etapa em execução e resumo final com duração.

Exemplos rápidos

- Importar CSV local para o banco com ingestão incremental (caso você já
  tenha um arquivo de dados e queira carregá-lo):

 ```bash
 poetry run main ingest-snapshot snapshots/PETR4_snapshot.csv --ticker PETR4
 ```

O comando também calcula checksum e evita reprocessar arquivos idênticos.
Quando houver cache válido, a CLI mostra explicitamente que a etapa foi
reutilizada.

- Exportar dados para CSV:

```bash
poetry run main export-csv --ticker PETR4
```

Durante a exportação, a CLI mostra leitura do banco, gravação do arquivo e o
local final do CSV.

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

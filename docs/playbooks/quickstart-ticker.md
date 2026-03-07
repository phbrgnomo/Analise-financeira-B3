# Quickstart: ingest → persist → snapshot → notebook

Este playbook descreve os passos mínimos para reproduzir o fluxo ingest→persist→snapshot→notebook usando um ticker de amostra.

Pré-requisitos
- Python 3.12+ (virtual env/poetry recomendado)
- Dependências instaladas: `poetry install` (ou conforme `pyproject.toml`)
- Banco local SQLite em `dados/data.db` (o projeto cria quando necessário)

Exemplo rápido

1. Executar ingest e persist (forçando refresh):

```bash
poetry run main pipeline ingest PETR4 --force-refresh
```

2. Arquivos/paths esperados (exemplos):
- Snapshot CSV: `snapshots/PETR4_snapshot.csv`
- Banco SQLite: `dados/data.db`
- Relatórios derivados: `reports/PETR4_report.csv` (quando aplicável)
- Raw provider CSVs: `raw/<provider>/<TICKER>-YYYYMMDDTHHMMSSZ.csv`
- Checksum ao lado do raw CSV: `raw/<provider>/<TICKER>-YYYYMMDDTHHMMSSZ.csv.checksum`
- Metadados de ingestão (JSONL, append-only): `metadata/ingest_logs.jsonl` (uma linha JSON por ingest com `job_id, source, fetched_at, raw_checksum, rows, filepath, status, created_at`)

Verificações mínimas

- Verificar existência do snapshot:

```bash
ls -l snapshots/PETR4_snapshot.csv
```

- Calcular checksum SHA256 do snapshot:

```bash
sha256sum snapshots/PETR4_snapshot.csv
# Exemplo de saída:
# e3b0c44298fc1c149afbf4c8996fb924...  snapshots/PETR4_snapshot.csv
```

Verificar raw provider e metadados

```bash
# a pasta raw usa o ticker no formato do provedor (yfinance inclui ".SA")
ls -l raw/yfinance/PETR4.SA-*.csv
# o comando CLI/ingest abaixo aceita o ticker base sem sufixo
# (PETR4) — a tradução é feita internamente pela fábrica de adapters
# ver última entrada JSONL
tail -n 1 metadata/ingest_logs.jsonl | jq '.'
```

Observação: a implementação atual grava metadados em `metadata/ingest_logs.jsonl` (JSON Lines append-only). Para exigir permissões owner-only nos artefatos, chame a função com `set_permissions=True` ou aplique `chmod 600` manualmente.

Banco de dados local
- Inicialize o banco SQLite (se ainda não existir):

```bash
poetry run python scripts/init_ingest_db.py --db dados/data.db
```

O pipeline também tenta persistir automaticamente as linhas canônicas no banco via `db.write_prices()` quando o mapeamento canônico e a validação forem bem-sucedidos.

- Abrir notebook de análise (ex.: `notebooks/quickstart.ipynb`) e executar células necessárias para gerar os plots esperados.

Comandos de troubleshooting

- Forçar ingest completo ignorando cache do pipeline:

```bash
poetry run main pipeline ingest PETR4 --force-refresh
```

Notas de exemplo e outputs

- Ao executar o quickstart, um CSV com colunas OHLCV e uma coluna `Return` deve ser persistido no snapshot.
- O checksum é usado para validação automatizada no CI (verificar `snapshots_test/` para exemplos e fixtures).

Checklist de verificação (mínimo)

- [ ] Executou o comando de ingest com sucesso
- [ ] Snapshot gerado em `snapshots/` com o nome esperado
- [ ] Checksum SHA256 calculado e conferido
- [ ] Notebook relacionado abre e gera os plots esperados

Referências
- Arquitetura: docs/planning-artifacts/architecture.md
- PRD: docs/planning-artifacts/prd.md

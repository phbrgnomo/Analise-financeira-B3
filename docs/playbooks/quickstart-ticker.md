# Quickstart: ingest → persist → snapshot → notebook

Este playbook descreve os passos mínimos para reproduzir o fluxo ingest→persist→snapshot→notebook usando um ticker de amostra.

Pré-requisitos
- Python 3.14+ (virtual env/poetry recomendado)
- Dependências instaladas: `poetry install` (ou conforme `pyproject.toml`)
- Banco local SQLite em `dados/data.db` (o projeto cria quando necessário)

Exemplo rápido

1. Executar ingest e persist (forçando refresh):

```bash
poetry run main --ticker PETR4.SA --force-refresh
```

2. Arquivos/paths esperados (exemplos):
- Snapshot CSV: `snapshots/PETR4_snapshot.csv`
- Banco SQLite: `dados/data.db`
- Relatórios derivados: `reports/PETR4_report.csv` (quando aplicável)

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

- Abrir notebook de análise (ex.: `notebooks/quickstart.ipynb`) e executar células necessárias para gerar os plots esperados.

Comandos de troubleshooting

- Forçar ingest completo e limpar cache:

```bash
poetry run main --ticker PETR4.SA --force-refresh --clear-cache
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

# Quickstart: Ingest → Persist → Snapshot → Notebook

Objetivo: permitir que um desenvolvedor reproduza o fluxo completo usando um ticker de exemplo em ≤ 30 minutos.

Pré-requisitos

- Python 3.14, Poetry instalado
- Dependências instaladas: `poetry install`
- Dados de amostra/fixtures disponíveis (opcional)

Passos rápidos

1. Executar ingest (exemplo):

```bash
poetry run main --ticker PETR4.SA --force-refresh
```

- Saída esperada: logs progressivos mostrando fetch rows, saved raw CSV (raw/yfinance/...), gravado em `dados/data.db` e snapshot em `snapshots/`.

2. Verificar artifacts gerados:

```bash
# listar snapshots
ls -l snapshots/ | tail -n 5

# checar checksum (exemplo)
sha256sum snapshots/PETR4.SA-*.csv
```

3. Abrir notebook de quickstart (ex.: `notebooks/quickstart.ipynb`) e executar células relevantes, passando `TICKER = "PETR4.SA"` como parâmetro.

Exemplo de verificação mínima

- O snapshot CSV deve conter colunas `date,open,high,low,close,adj_close,volume`
- O comando `poetry run main --ticker PETR4.SA --force-refresh` deve terminar com código de saída `0` e log `Snapshot saved: snapshots/PETR4.SA-<ts>.csv`

Dicas de debugging

- Se o adaptador falhar, examine `raw/<provider>/` para o CSV bruto e `ingest_logs` para mensagens de erro.
- Use `--dry-run` para validar fetch e mapeamento sem gravar no DB.

Referências

- docs/planning-artifacts/prd.md
- docs/planning-artifacts/epics.md

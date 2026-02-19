# UX Playbook (mínimo)

Este documento descreve as expectativas mínimas de UX para CLI, notebooks e uma tela Streamlit simples.

CLI

- Flags suportadas (exemplos):
  - `--ticker <TICKER>` (ex.: PETR4.SA)
  - `--force-refresh` (força re-ingest)
  - `--output <path>` (local de saída dos artefatos)

- Mensagens esperadas (stdout/stderr):
  - Início do processo: `INFO: Starting ingest for <TICKER>`
  - Success: `INFO: Snapshot saved to <path>`
  - Warnings: `WARN: Incomplete data for <date>`
  - Errors: `ERROR: Failed to fetch data for <TICKER> - <reason>`

Notebooks

- Parâmetros esperados (exemplos):
  - `ticker = "PETR4.SA"`
  - `start_date = "2020-01-01"`
  - `end_date = "2020-12-31"`

- Comportamento esperado:
  - Células de preparação carregam o snapshot CSV localizado em `snapshots/`
  - Células de análise computam retornos e geram ao menos um plot de preços ajustados e um plot de retornos

Streamlit (minimal)

- Telas mínimas:
  1. Tela de seleção de ticker e período
  2. Tela de execução com botão `Run` e área de logs/saídas
  3. Visualização de um gráfico principal e resumo numérico (último preço, retorno 1d)

- Interações esperadas:
  - Ao clicar `Run`, mostrar mensagem `Processing...` e desabilitar inputs até finalizar
  - Exibir mensagens de sucesso/erro conforme CLI

Exemplos de saída (stdout)

```
INFO: Starting ingest for PETR4.SA
INFO: Downloaded 1200 rows for PETR4.SA
INFO: Snapshot saved to snapshots/PETR4_snapshot.csv
INFO: Checksum: e3b0c44298fc1c149afbf4c8996fb924...
```

Notas

- Mensagens devem ser concisas e JSON-parseable quando `--verbose-json` for usado (opcional)
- Use logging estruturado para facilitar parsing em CI/monitoring

Checklist (mínimo)

- [ ] Documentou flags CLI e mensagens esperadas
- [ ] Documentou parâmetros de notebook e comportamento esperado
- [ ] Documentou telas mínimas do Streamlit e interações

Referências
- docs/playbooks/quickstart-ticker.md

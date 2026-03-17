# UX Playbook (mínimo)

Este documento descreve as expectativas mínimas de UX para CLI, notebooks e uma tela Streamlit simples.

## CLI

- Flags suportadas (exemplos):
  - `--ticker <TICKER>` (ex.: PETR4, ITUB4, BOVA11)
  - `--start_date <YYYY-MM-DD>` (para limitar o intervalo de dados)
  - `--end_date <YYYY-MM-DD>` (para limitar o intervalo de dados)
  - `--force-refresh` (força re-ingest)
  - `--format <text|json>` (formato de saída, padrão `text`)
  - `--no-network` (modo offline para testes/CI usando provider dummy)
  - `--output <path>` (local de saída para `export-csv`)

- Mensagens esperadas (stdout/stderr):
  - Início do processo: `Executando tickers padrão: ...`
  - Success: `Resumo run: sucesso=<n>, falhas=<n>`
  - Warnings: `WARN: Incomplete data for <date>`
  - Errors: `ERROR: Failed to fetch data for <TICKER> - <reason>`

## Notebooks

- Parâmetros esperados (exemplos):
  - `ticker = "PETR4"`
  - `start_date = "2020-01-01"`
  - `end_date = "2020-12-31"`

- Comportamento esperado:
  - Células de preparação carregam o snapshot CSV localizado em `snapshots/`
  - Células de análise computam retornos e geram ao menos um plot de preços ajustados e um plot de retornos

## Streamlit (minimal)

- Telas mínimas:
  1. Tela de seleção de ticker e período
  2. Tela de execução com botão `Run` e área de logs/saídas
  3. Visualização de um gráfico principal e resumo numérico (último preço, retorno 1d)

- Interações esperadas:
  - Ao clicar `Run`, mostrar mensagem `Processing...` e desabilitar inputs até finalizar
  - Exibir mensagens de sucesso/erro conforme CLI

## Exemplos de saída (stdout)

```
Executando tickers padrão: PETR4, ITUB3, BBDC4
PETR4.SA: 250 retornos persistidos
Resumo run: sucesso=1, falhas=0
```

## Notas

- Mensagens devem ser concisas e orientadas a troubleshooting
- Use logging estruturado para facilitar parsing em CI/monitoring

## Checklist (mínimo)

- [ ] Documentou flags CLI e mensagens esperadas
- [ ] Documentou parâmetros de notebook e comportamento esperado
- [ ] Documentou telas mínimas do Streamlit e interações

## Referências
- docs/playbooks/quickstart-ticker.md

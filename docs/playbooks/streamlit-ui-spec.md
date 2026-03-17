# Streamlit UI Contract (POC)

Este documento descreve o contrato mínimo de UI para o POC Streamlit do projeto.

## 1. Objetivo

O Streamlit POC deve permitir ao usuário:
- selecionar um ticker B3 (ex.: `PETR4`, `ITUB3`)
- selecionar um intervalo de datas (`start_date`, `end_date`)
- executar a ingestão/consulta e visualizar resultados (gráficos, tabelas)
- baixar o snapshot gerado (CSV + checksum)

## 2. Controles e telas

### 2.1 Seletor de ticker e período

- **Dropdown ou autocomplete**: lista de tickers (obter de `DEFAULT_TICKERS` ou da base de dados)
- **Data de início**: `start_date` (YYYY-MM-DD)
- **Data de fim**: `end_date` (YYYY-MM-DD)
- **Botão**: `Run` (texto exato)
- **Checkbox**: `Use mock data` (habilita modo offline / fixtures)

### 2.2 Feedback / logs

- Ao clicar em `Run`, mostrar texto `Processing...` e desabilitar inputs.
- Exibir mensagens de sucesso/em erro da mesma forma que a CLI (mensagens simples, sem códigos de escape):
  - `✅ Done: snapshot saved to <path>`
  - `❌ Error: <mensagem>`

### 2.3 Output principal

- Gráfico de preços (OHLC ou linhas de fechamento).
- Gráfico de retornos diários (ou tabela resumida).
- Parágrafo com dados chave:
  - `Snapshot:` caminho do arquivo gerado (ex.: `snapshots/PETR4-20260215.csv`)
  - `Checksum:` valor SHA256
  - `Rows:` número de linhas
  - `Duration:` tempo de execução em segundos

### 2.4 Download

- Botão `Download CSV` que fornece o snapshot gerado.
- Botão `Download Checksum` que fornece o conteúdo do `.checksum`.

## 3. JSON summary contract (para logs/integração)

O Streamlit deve gerar (internamente, para logs) um JSON que segue o contrato abaixo:

```json
{
  "job_id": "<uuid>",
  "status": "success|warning|failure",
  "ticker": "PETR4",
  "snapshot_path": "snapshots/PETR4-20260215.csv",
  "checksum": "<sha256>",
  "rows": 1234,
  "duration_sec": 12.3
}
```

## 4. Erros

Quando ocorrer um erro, o JSON de log deve conter o campo `error` com a mensagem, e o status deve ser `failure`.

## 5. Notas de implementação

- Para garantir testabilidade, separa a lógica de carregamento/transformação de dados em funções reutilizáveis (e.g., `load_snapshot(ticker, start_date, end_date)`), que podem ser chamadas por testes sem executar a UI.
- A interface pode ser implementada com `streamlit` ou outra biblioteca similar, mas deve ser fácil de adaptar para uma UI futura.

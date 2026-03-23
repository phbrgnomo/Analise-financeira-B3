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
- **Campo livre (opcional)**: permite digitar um ticker livremente; deve ser normalizado/validado usando a mesma regra de B3 usada pela CLI (`normalize_b3_ticker`).
  - **Ticker inválido** (formato não-B3, ex.: ``PETR`` ou ``PETR4-``) deve travar a execução e exibir mensagem de erro clara.
  - **Ticker ausente na base de dados**: o UI deve permitir o uso (para casos em que o usuário quer forçar ingestão de um novo ticker), mas o fluxo deve tratar o caso como "sem dados" se não houver série histórica.
- **Data de início**: `start_date` (YYYY-MM-DD)
- **Data de fim**: `end_date` (YYYY-MM-DD)

Validação de datas (deve ocorrer antes de executar o pipeline):
- `start_date` e `end_date` devem ser datas válidas no formato `YYYY-MM-DD`.
- `start_date` não pode ser após `end_date`.
- Nenhuma data pode ser no futuro (maior que hoje).
- Deve haver um **intervalo máximo permitido** (ex.: 365 dias) para evitar consultas muito pesadas e uso excessivo de API/CPU. Se o intervalo exceder o máximo, deve aparecer um erro explicando o limite.

- **Botão**: `Run` (texto exato)
- **Checkbox**: `Use mock data` (habilita modo offline / fixtures)
  - Quando ativado, o pipeline usa o provider `dummy` (dados sintéticos). Isso **não faz chamadas de rede** e gera um pequeno DataFrame fixo, independentemente do ticker/datas fornecidos (desde que o ticker passe na validação de formato).

### 2.2 Feedback / logs

- Ao clicar em `Run`, mostrar texto `Processing...` e desabilitar inputs.
- Exibir mensagens de sucesso/erro da mesma forma que a CLI (mensagens simples, sem códigos de escape):
  - `✅ Done: snapshot saved to <path>`
  - `❌ Error: <mensagem>`

Mensagens de erro específicas que devem ser exibidas em cada caso:
- **Ticker inválido**: `❌ Error: ticker inválido (ex.: PETR4)`
- **Data inválida / intervalo inválido**: `❌ Error: start_date deve ser anterior ou igual a end_date` ou `❌ Error: datas não podem ser futuras` ou `❌ Error: intervalo máximo de 365 dias excedido`.
- **Sem dados para o período**: `❌ Error: nenhum dado disponível para o período selecionado` (ou `✅ Done: nenhum retorno calculado` no caso de status warning).
- **Falha ao gravar snapshot** (ex.: permissão, disco cheio): `❌ Error: falha ao salvar snapshot: <mensagem técnica>`.

### 2.3 Output principal

- Gráfico de preços (OHLC ou linhas de fechamento).
- Gráfico de retornos diários (ou tabela resumida).
- Parágrafo com dados chave:
  - `Snapshot:` caminho do arquivo gerado (ex.: `snapshots/PETR4-20260215.csv`)
  - `Checksum:` valor SHA256
  - `Rows:` número de linhas
  - `Duration:` tempo de execução em segundos

#### Estado vazio / sem dados

Quando o período selecionado não retorna dados (por exemplo, ticker desconhecido, intervalo fora da base histórica ou filtro de data que não cobre registros):
- Mostrar um estado vazio / mensagem clara como `Nenhum dado disponível para o período selecionado`.
- Desabilitar os botões de download (CSV e Checksum) e não exibir uma URL de snapshot.

### 2.4 Download

- Botão `Download CSV` que fornece o snapshot gerado.
- Botão `Download Checksum` que fornece o conteúdo do `.checksum`.

#### Comportamento em modo mock (`Use mock data`)

- O pipeline sempre gera um snapshot sintético (3 linhas); portanto, os downloads devem estar habilitados quando a execução é bem-sucedida.
- Se ocorrer erro de validação (ticker inválido, data inválida, etc.), o UI deve impedir a execução e não habilitar os downloads.

## 3. JSON summary contract (para logs/integração)

O Streamlit deve gerar (internamente, para logs) um JSON que segue o contrato abaixo. Cada campo deve obedecer às regras descritas em seguida.

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

### Regras de validação por campo

- **job_id**: string obrigatória em formato UUID (8-4-4-4-12 hex); ex.: `123e4567-e89b-12d3-a456-426614174000`.
- **status**: string obrigatória. Valores permitidos:
  - `success`: ingestão e persistência concluídas com sucesso.
  - `warning`: ingestão concluída, mas alguma condição recuperável (ex.: nenhum retorno calculado, dados parciais).
  - `failure`: ingestão abortada por erro (ex.: falha de rede, ticker inválido, timeout).
- **ticker**: string obrigatória; ticker B3 normalizado (ex.: `PETR4`).
- **snapshot_path**: string opcional. Caminho do arquivo CSV gerado. Pode estar ausente em casos de falha.
- **checksum**: string opcional. SHA-256 em hex (64 caracteres). Deve aparecer somente se `snapshot_path` for gerado.
- **rows**: inteiro >= 0 obrigatoriamente presente. Número de linhas de retorno persistidas.
- **duration_sec**: número >= 0 obrigatoriamente presente. Tempo de execução em segundos.

### Critérios de status (success/warning/failure)

- **success**: tudo fluiu, retornos calculados e persistidos normalmente.
- **warning**: operação completou, mas houve condições menores que são relevantes (ex.: nenhum retorno foi calculado porque não havia dados no período, ou validação de dados gerou avisos).
- **failure**: a ingestão/parada ocorreu por erro não recuperável (rede, erro do provedor, ticker inválido, falha de escrita).

### Exemplos de payloads completos

#### Success
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "success",
  "ticker": "PETR4",
  "snapshot_path": "snapshots/PETR4-20260215.csv",
  "checksum": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
  "rows": 1234,
  "duration_sec": 12.3
}
```

#### Warning (sem retornos)
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "warning",
  "ticker": "PETR4",
  "snapshot_path": null,
  "checksum": null,
  "rows": 0,
  "duration_sec": 2.1
}
```

#### Failure (erro de rede)
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "failure",
  "ticker": "PETR4",
  "snapshot_path": null,
  "checksum": null,
  "rows": 0,
  "duration_sec": 0.7,
  "error": "NetworkError: timeout ao obter dados"
}
```

### Limitações e validações adicionais

- **Tamanho máximo**: o payload deve permanecer razoável (não incluir grandes blobs de dados) para que seja manipulado facilmente em logs.
- **Timestamp / job_id**: o `job_id` deve ser gerado como UUID para facilitar rastreabilidade;
  o campo `duration_sec` deve ser >= 0.
- **Consistency check (checksum / snapshot_path)**: se `snapshot_path` estiver presente, o `checksum` deve ser um SHA-256 válido e corresponder ao arquivo gerado; caso contrário, os campos devem ser `null`.
- **Retries / backoff**: quando status `failure` for devido a erros transitórios (rede/timeout), a camada de ingest deve aplicar retry com backoff exponencial (ex.: 3 tentativas).
## 4. Erros

Quando ocorrer um erro, o JSON de log deve conter:

- `status`: sempre `"failure"`.
- `error`: mensagem ou objeto descrevendo a causa.

### Exemplos de payloads de erro

#### 4.1 Network failure (timeout/rede)
```json
{
  "status": "failure",
  "error": "NetworkError: timeout ao buscar dados",
  "ticker": "PETR4"
}
```

#### 4.2 Ticker inválido / não encontrado
```json
{
  "status": "failure",
  "error": "InvalidTickerError: ticker inválido ou sem dados históricos",
  "ticker": "XYZ123"
}
```

#### 4.3 Timeout ou falha de provider remoto
```json
{
  "status": "failure",
  "error": "TimeoutError: provider não respondeu em 30s",
  "ticker": "PETR4"
}
```

### Tipos de erro esperados (não-exaustivo)

- **NetworkError**: falha de conexão (timeout, DNS, sem acesso à internet).
- **InvalidTickerError**: ticker inválido ou ausente na base de dados histórica.
- **TimeoutError**: chamada ao provedor demorou demais.

### Estratégia de recuperação e retry

- Recomenda-se implementar **retry com backoff exponencial** para erros transitórios (NetworkError, TimeoutError).
- Limite de retries deve ser pequeno (ex.: 3 tentativas) para evitar sobrecarga em APIs externas.
- O processo deve ser **idempotente**: repetir a mesma chamada não deve causar resultados diferentes ou duplicados.

### Limitações e casos de borda

- Se o erro for relacionado a validação local (ticker inválido, intervalo de datas), **não** deve haver retry automático.
- Para falhas de gravação de snapshot (p.ex. disco cheio), o UI deve exibir a mensagem de erro e permitir que o usuário tente novamente depois de corrigir o ambiente.

## 5. Notas de implementação

- Para garantir testabilidade, separa a lógica de carregamento/transformação de dados em funções reutilizáveis (e.g., `load_snapshot(ticker, start_date, end_date)`), que podem ser chamadas por testes sem executar a UI.
- A interface é um POC em `streamlit`; outras opções incluem `gradio` (rápido para protótipos) ou `flask`/`fastapi` (para integração como serviço web). A escolha deve priorizar simplicidade e facilidade de evolução para uma UI futura.

# CLI Contract (Quickstart / Health / JSON Output)

Este documento define o contrato de saída JSON e códigos de retorno para os comandos principais da CLI usados no quickstart e em automação (CI).

## 1. Quickstart JSON summary (`--format json`)

O comando principal `main run` (ou seu atalho `main --ticker <TICKER>`) aceita a flag `--format json` para emitir apenas um objeto JSON estruturado. Isso permite validação automática em pipelines.

### Schema JSON (Quickstart summary)

```json
{
  "status": "success|warning|failure",
  "job_id": "<uuid>",
  "duration_sec": 0.0,
  "tickers": [
    {
      "ticker": "PETR4",
      "provider": "yfinance",
      "status": "success|warning|failure",
      "rows_ingested": 123,
      "rows_returns": 120,
      "snapshot_path": "snapshots/PETR4-20260215.csv",
      "snapshot_checksum": "<sha256>",
      "error_message": null
    }
  ]
}
```

### Campos obrigatórios

- `status` (string): `success`, `warning`, ou `failure`
- `job_id` (string): UUID único para o run
- `duration_sec` (number): tempo total em segundos
- `tickers` (array): lista de resultados por ticker

### Campos por ticker

- `ticker` (string)
- `provider` (string)
- `status` (string): `success`, `warning`, `failure`
- `rows_ingested` (int)
- `rows_returns` (int)
- `snapshot_path` (string) — caminho do arquivo snapshot gerado (ou `null` se não houver)
- `snapshot_checksum` (string) — checksum SHA256 do snapshot (ou `null`)
- `error_message` (string|null)

## 2. Exit Codes

A CLI deve usar os seguintes códigos de saída (exit codes):

- `0` — execução bem-sucedida (todos os tickers com `status=success`)
- `1` — execução com avisos (pelo menos um ticker com `status=warning`, nenhum `status=failure`)
- `2` — execução com falha (algum ticker com `status=failure` ou erro fatal)

## 3. Flags relevantes

- `--format json` — força saída JSON conforme schema acima (em vez de mensagens de texto). (Default: `text`)
- `--ticker <TICKER>` — ticker principal a ser processado. Quando omitido, usa `DEFAULT_TICKERS`.
- `--force-refresh` — força refetch/refresh ignorando cache e snapshots.
- `--no-network` — (modo de teste) força uso de provider `dummy` que não faz chamadas de rede.

## 4. Comportamento esperado

- O comando deve ser determinístico para a mesma entrada e condições (especialmente em modo `--no-network`).
- Em modo `--format json`, nada além do JSON deve ser impresso em stdout.
- Mensagens de log e erros (quando não em JSON) devem ser impressas no stderr.

## 5. Integração CI

Scripts e jobs de CI devem invocar:

```bash
poetry run main --ticker PETR4 --format json --no-network
```

E validar o JSON retornado contra o schema acima.

## 6. Limitações e edge cases

### Limites operacionais

- **Número máximo de tickers por execução**: o comando deve suportar trabalhar com `DEFAULT_TICKERS` (tipicamente 3-5 tickers) de forma confiável. Listas muito grandes (> 20) podem causar uso elevado de memória e tempo de execução; recomenda-se particionar em múltiplas execuções.
- **Memória/CPU**: cada ticker pode gerar um DataFrame em memória (tamanho proporcional ao número de dias retornados). Em cargas grandes, espere consumo de RAM na ordem de dezenas de MB por ticker e uso de CPU para cálculos/serialização do JSON.

### Validações de entrada (`--ticker`)

- Valores devem seguir o formato B3 (letras+digitos, ex.: `PETR4` ou `BOVA11`). A CLI normaliza para maiúsculas.
- Não são permitidos caracteres especiais/extras (ex.: `PETR4-`, `PETR_4`).
- Comprimento máximo: tipicamente até 6-7 caracteres (padrão B3); valores muito longos devem ser rejeitados.

### Timeout / retries / falhas de rede

- **Modo normal (padrão)**:
  - A ingestão tenta conectar-se ao provedor (ex.: yfinance) e pode aplicar retries.
  - Erros transitórios (NetworkError, TimeoutError) devem ser re-tentados (ex.: até 3 vezes com backoff exponencial).
  - Em caso de persistência de erro, o ticker finaliza com `status=failure` e `error_message` descrevendo o motivo.

- **Modo `--no-network`**:
  - Usa provider `dummy`, que não faz chamadas de rede e deve ser determinístico.
  - Não deve haver retries ou timeouts relacionados a rede.

### Comportamento do JSON em falhas / tempo limite

- Se a execução terminar com falha de rede/timeout, o JSON deve retornar `status=failure` e incluir `error_message` detalhando o problema.
- A CLI deve usar o código de saída `2` nesses casos, alinhado ao contrato.

### Malformações de JSON e consumidores

- O CLI **deve** produzir JSON válido quando `--format json` for usado; qualquer saída extra (logs, warnings) deve ir para stderr.
- Consumidores devem assumir que qualquer saída não-JSON (ou JSON inválido) indica uma falha de execução.

### Consistência checksum/snapshot

- Quando `snapshot_path` e `checksum` são retornados, espera-se que:
  - `snapshot_path` aponte para um arquivo existente gerado pela execução
  - `checksum` seja um SHA256 hexadecimal válido de 64 caracteres e corresponda ao arquivo indicado
- Se o snapshot não pôde ser gerado, `snapshot_path` e `checksum` devem ser `null`.

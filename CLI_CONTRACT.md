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
  "ticks": [
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
- `ticks` (array): lista de resultados por ticker

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

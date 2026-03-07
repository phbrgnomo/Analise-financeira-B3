# YFinance Adapter

Este documento descreve o comportamento do adaptador `YFinanceAdapter` e as configurações de retry/backoff disponíveis via variáveis de ambiente.

Configuração via variáveis de ambiente (padrão `ADAPTER_RETRY_*`):

- ADAPTER_RETRY_MAX_ATTEMPTS: número máximo de tentativas (padrão: 3)
- ADAPTER_RETRY_INITIAL_DELAY_MS: delay inicial em ms (padrão: 1000)
- ADAPTER_RETRY_MAX_DELAY_MS: delay máximo em ms (padrão: 30000)
- ADAPTER_RETRY_BACKOFF_FACTOR: fator de backoff (padrão: 2.0)
- ADAPTER_RETRY_ON_STATUS_CODES: lista de códigos HTTP separados por vírgula que devem acionar retry (padrão: 429,500,502,503,504)
- ADAPTER_RETRY_TIMEOUT_SECONDS: timeout total para a operação em segundos (padrão: 30)

Exemplo de uso (bash):

```bash
export ADAPTER_RETRY_MAX_ATTEMPTS=5
export ADAPTER_RETRY_INITIAL_DELAY_MS=500
export ADAPTER_RETRY_BACKOFF_FACTOR=2.0
poetry run main  # ou executar script que instancia YFinanceAdapter
```

Exemplo de uso em código:

```python
from src.adapters.yfinance_adapter import YFinanceAdapter

# Instancia o adaptador (se não passar parâmetros, ele lê da configuração de ambiente)
adapter = YFinanceAdapter()

df = adapter.fetch("PETR4", start_date="2024-01-01", end_date="2024-12-31")
print(df.head())
```

Observações:
- Retries só devem ser habilitados para operações idempotentes por padrão. Se a operação não for idempotente, passe `idempotent=False` ao chamar o helper de retry (internamente o adaptador garante não executar retries nestes casos).
- Logs estruturados são emitidos em cada tentativa com informações: `attempt`, `next_delay_ms`, `error_message`.
- Métricas agregadas estão disponíveis via `src.adapters.retry_metrics.get_global_metrics()`.

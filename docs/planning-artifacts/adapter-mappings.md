# Adapter Mappings

Este arquivo documenta exemplos de mapeamento entre provedores de dados e o esquema canônico usado pelo projeto.

## Propósito

- Padronizar como campos retornados por diferentes provedores são traduzidos para as tabelas canônicas (`prices`, `returns`, etc.).
- Facilitar a adição de novos provedores sem alterar a camada de persistência.
- Servir como referência para testes e validação de adaptadores.

## Exemplo: yfinance -> Canonical

Provedor: `yfinance` (via `yfinance.download`)

Campos brutos típicos retornados por `yfinance` (por ticker agrupado):
- `Open`, `High`, `Low`, `Close`, `Adj Close`, `Volume` (índice: `Date`)

Mapping canônico sugerido para a tabela `prices`:

- `ticker` (adicionado pelo adaptador)  <- constante informada na chamada
- `date` (index convertido para coluna, tipo DATE)  <- `Date`
- `open` <- `Open`
- `high` <- `High`
- `low` <- `Low`
- `close` <- `Close`
- `adj_close` <- `Adj Close`
- `volume` <- `Volume`
- `source` <- `'yfinance'`
- `fetched_at` <- timestamp de ingestão (UTC)
- `raw_checksum` <- SHA256 do payload/CSV bruto salvo para auditoria
- `raw_response_path` <- caminho para o arquivo raw salvo (opcional)

Observações:
- Tipos devem ser normalizados: datas em ISO `YYYY-MM-DD`, números como `REAL`, volumes como `INTEGER` quando possível.
- Colunas adicionais retornadas pelo provedor podem ser preservadas em `raw_response` ou mapeadas para campos auxiliares conforme necessário.

### Exemplo de código (uso do canonical mapper)

```python
from src.adapters.yfinance_adapter import YFinanceAdapter
from src.etl.mapper import to_canonical

# Buscar dados brutos
adapter = YFinanceAdapter()
raw_df = adapter.fetch("PETR4.SA", start_date="2026-01-01", end_date="2026-01-31")

# Converter para schema canônico
canonical_df = to_canonical(raw_df, provider_name="yfinance", ticker="PETR4.SA")

# canonical_df agora tem colunas: ticker, date, open, high, low, close,
# adj_close, volume, source, fetched_at
# e metadata em canonical_df.attrs: raw_checksum, provider, ticker

# Usar com camada de persistência
from src.db.db import write_prices
write_prices(canonical_df)  # Upsert no SQLite
```

## Exemplo: Alpha Vantage -> Canonical

Provedor: `Alpha Vantage` (TIME_SERIES_DAILY_ADJUSTED)

Notas de mapeamento:
- A resposta JSON contém campos com prefixos numéricos (`1. open`, `2. high`, ...). O adaptador deve extrair e renomear para os campos canônicos acima.
- Respeitar limites de taxa: adaptador deve suportar backoff configurável e caching local de respostas brutas.

## Checklist para adicionar novo provedor

- [ ] Implementar `Adapter.fetch(ticker) -> pd.DataFrame(raw)` que salva também o `raw_response` localmente.
- [ ] Implementar `Adapter.normalize(df_raw) -> df_canonical` seguindo os mapeamentos documentados.
- [ ] Atualizar `docs/planning-artifacts/adapter-mappings.md` com o novo provedor e um exemplo de mapping.
- [ ] Criar testes de contrato que usam o `df_canonical` esperado e validam `write_prices`/`upsert`.

## Notas finais

Manter este arquivo próximo ao desenvolvimento dos adaptadores garante que o esquema canônico evolua de forma documentada e testável.

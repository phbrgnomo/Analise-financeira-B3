Plan: Implementar Adapter e adaptador yfinance mínimo

TL;DR — Criar interface `Adapter` e um adaptador `yfinance` que retorne um `pandas.DataFrame` com metadados `source` e `fetched_at`. Usaremos `yfinance` (`yf.download`) como provider principal. Testes unitários usam fixtures CSV existentes para evitar chamadas de rede.

Steps
1. Criar pacote de adapters:
   - Adicionar `src/adapters/__init__.py` (tornar pacote e expor versão/exports).
2. Definir interface/erro:
   - Criar `src/adapters/base.py` com `class Adapter(ABC)` e método público `fetch(ticker: str) -> pd.DataFrame`.
   - Documentar contrato: DataFrame OHLCV/Adj Close e sem persistência.
   - Referenciar `AdapterError` nos docstrings.
   - Criar `src/adapters/errors.py` com `AdapterError` (atributos: message, code, original_exception).
3. Implementar adaptador provider:
   - Criar `src/adapters/yfinance_adapter.py` com `class YFinanceAdapter(Adapter)`.
   - Implementação:
   - Tentar `import yfinance as yf` — se disponível, usar `yf.download(...)`.
   - Não depender de `pandas_datareader` — usar wrapper compatível para facilitar mocks em testes.
     - Normalizar colunas para garantir presença de `['Open','High','Low','Close','Adj Close','Volume']` quando aplicável.
     - Setar metadados: `df.attrs['source'] = 'yahoo'` e `df.attrs['fetched_at'] = fetched_at_utc_iso`.
     - Retries simples (até 3 tentativas) com backoff exponencial mínimo; levantar `AdapterError` com códigos descritivos em falhas.
     - Logging via `logging` (usar logger `src.adapters`).
4. Logging mínimo:
   - Criar/atualizar `src/logging_config.py` ou usar `logging.basicConfig()` no adaptador para garantir mensagens testáveis (não alterar global behavior do projeto).
5. Testes:
   - Criar `tests/test_adapters.py`.
   - Testes:
   - Mockar o wrapper `web.DataReader` ou `yfinance` para retornar DataFrame carregado de `tests/fixtures/sample_ticker.csv`.
     - Verificar que `fetch()` retorna `pd.DataFrame`, contém colunas mínimas e `df.attrs['source'] == 'yahoo'` e `fetched_at` em UTC ISO8601.
     - Testar raising de `AdapterError` quando DataReader lança exceção.
   - Reutilizar fixtures existentes em `tests/fixtures/`.
6. Documentação:
   - Atualizar `docs/implementation-artifacts/1-1-implementar-interface-de-adapter-e-adaptador-yfinance-minimo.md` com contrato, exemplos de uso e códigos de erro.
7. Clean-up / integração:
   - Executar `poetry run pytest` e ajustar conforme erros.
   - Opcional: abrir PR com descrição e referência à Issue #114.

Verification
- Rodar testes unitários (local):
```bash
poetry install
poetry run pytest -q
```
- Rodar apenas testes do adaptador:
```bash
poetry run pytest tests/test_adapters.py -q
```
- Verificar linter/format:
```bash
poetry run ruff check .
poetry run black --check .
```

Decisions
- Dependência: usar `yfinance` como provider principal. Não usar `pandas-datareader` no código novo.
- Assinatura pública: `Adapter.fetch(ticker: str) -> pd.DataFrame` (conforme Acceptance Criteria).
- Nome/arquitetura: manter arquivo `yfinance_adapter.py` (compatível com story) mas implementar via DataReader por padrão; expor `YFinanceAdapter`.
- Erros: padronizar com `AdapterError` (mensagem, code, original_exception).
- Metadados: usar `df.attrs['source']` e `df.attrs['fetched_at']` (UTC ISO8601).

# Guia de Implementação — Adaptadores de Provedores

Objetivo: documentar o contrato, convenções e melhores práticas para implementar novos adaptadores de provedores de dados (ex.: Yahoo, AlphaVantage) neste repositório.

**Visão geral**
- Local: `src/adapters/`
- Contrato público: implementar um adaptador que herda de `Adapter` (`src/adapters/base.py`).
- Responsabilidade do adaptador: buscar dados brutos (OHLCV + `Adj Close`), retornar `pandas.DataFrame` com `DatetimeIndex` e preencher `DataFrame.attrs` com metadados.

**Assinaturas e métodos obrigatórios**
- `fetch(self, ticker: str, **kwargs) -> pd.DataFrame` (método público):
  - Normaliza argumentos (p.ex. ticker, datas).
  - Deve delegar ao mecanismo de retry do `Adapter` base ou chamar `_fetch_once` diretamente quando apropriado.
  - Deve preencher metadados em `df.attrs`:
    - `source`: provedor (ex.: `yahoo`)
    - `ticker`: ticker usado
    - `fetched_at`: timestamp ISO UTC
    - `adapter`: nome da classe do adaptador

- `@abstractmethod _fetch_once(self, ticker: str, start: str, end: str, **kwargs) -> pd.DataFrame` (hook protegido exigido):
  - Implementação concreta: executar uma única chamada ao provedor e retornar o DataFrame bruto.
  - Não trate retries aqui — o `Adapter._fetch_with_retries` encapsula retry/backoff, validações e mapeamento de exceções.

**Helpers fornecidos pelo `Adapter` base**
- `_fetch_with_retries(self, ticker, start, end, log_context=None, max_retries=3, backoff_factor=2.0, timeout=None, required_columns=None, **kwargs)`
  - Faz loop de retry/backoff, chama `_fetch_once` e aplica `_validate_dataframe`.
  - Mapeia exceções para `NetworkError` e `FetchError`.
- `_normalize_date(self, date_str: str) -> str` — normalização e validação de formatos aceitos (`YYYY-MM-DD` e `MM-DD-YYYY`).
- `_validate_dataframe(self, df, ticker, required_columns=None)` — validações genéricas (não vazio, presença de colunas OHLCV padrão, índice DatetimeIndex). Passe `required_columns` se o provedor usar nomes diferentes.

**Regras de design**
- Provider-specific logic (p.ex. sufixo `.SA` para B3) deve ficar no adaptador concreto:
  - Implementar `def _normalize_ticker(self, ticker: str) -> str` no adaptador, não no base.
- Evite captura indiscriminada de `Exception`; prefira tratar explicitamente erros conhecidos para decidir retry vs fail-fast.
- Use o mecanismo de retry do base; não reimplemente lógica de retry em cada adaptador.

**Compatibilidade e testes**
- Tests do projeto usam monkeypatch/patch em `src.adapters.yfinance_adapter.web.DataReader`. Para manter compatibilidade durante testes, o adaptador do Yahoo mantém um shim `web.DataReader`. Novos adaptadores podem expor shims similares ou aceitar a injeção do `fetcher` via construtor.
- Escreva testes que verifiquem o comportamento público (`fetch`) preferencialmente. Se for necessário testar helpers, importe diretamente os helpers do local correto (`Adapter._normalize_date` agora vive no base).
- Não dependa de mensagens de erro exatas nos testes; prefira asserções sobre o tipo da exceção e atributos estruturados quando possível.

**Metadados e observabilidade**
- Logging: envie `log_context` com `ticker`, intervalo e tentativa atual ao chamar `_fetch_with_retries`. Use `logger` do módulo.
- Exponha `get_metadata()` retornando `provider`, `library`, `library_version`, `library_available` e parâmetros relevantes (`max_retries`, `backoff_factor`).

**Exemplo mínimo (pseudocódigo)**
```python
class MeuAdapter(Adapter):
    def __init__(self, ...):
        self.max_retries = 3
        self.backoff_factor = 2.0
        self.timeout = 30

    def fetch(self, ticker, start_date=None, end_date=None, **kwargs):
        t = self._normalize_ticker(ticker)
        s = self._normalize_date(start_date or default_start)
        e = self._normalize_date(end_date or default_end)
        log_ctx = {"ticker": t, "provider": "meu"}
        df = super()._fetch_with_retries(t, s, e, log_context=log_ctx, max_retries=self.max_retries, backoff_factor=self.backoff_factor, timeout=self.timeout)
        df.attrs["source"] = "meu"
        df.attrs["ticker"] = t
        df.attrs["fetched_at"] = now_iso_utc()
        df.attrs["adapter"] = self.__class__.__name__
        return df

    def _fetch_once(self, ticker, start, end, **kwargs):
        # chamada direta ao cliente do provedor
        return cliente.download(ticker, start=start, end=end)

    def _normalize_ticker(self, ticker):
        return ticker.upper()
```

**Migração / notas operacionais**
- Se seu adaptador anterior implementava retry internamente, remova essa lógica e implemente `_fetch_once` para delegar retry ao base.
- Ao adicionar um novo adaptador, rode a suíte de testes e adicione testes específicos no `tests/` para garantir compatibilidade com o harness de contratos.

**Onde documentar alterações**
- Atualize `docs/implementation-artifacts/` com o arquivo acima e, se necessário, inclua exemplos em `docs/playbooks/`.

---

Se quiser, eu crio também um checklist de PR (arquivo `docs/implementation-artifacts/adapter-pr-checklist.md`) com itens de verificação para reviewers (tests, mensagens de erro, docs, metadados). Quer que eu gere esse checklist também?

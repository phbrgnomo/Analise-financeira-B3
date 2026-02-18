---
stepsCompleted: [1, 2, 3, 4, 5]
lastStep: 5
stepsCompleted: []
inputDocuments: []
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'techstack-implementacao-b3'
research_goals: 'definir qual o techstack ideal para a implementacao da ideia'
user_name: 'Phbr'
date: '2026-02-15'
web_research_enabled: true
source_verification: true
---

# Research Report: technical

**Date:** 2026-02-15
**Author:** Phbr
**Research Type:** technical

---

## Research Overview

Objetivo: definir o techstack ideal para a implementação da ferramenta de aprendizado para coleta e análise de dados da B3.

---

## Sources to be used
- pandas documentation
- pandas-datareader / yfinance
- SQLite documentation
- SQLAlchemy documentation
- Streamlit documentation
- PyPortfolioOpt
- CVXPY
- SciPy optimize

---

## Next steps
1. Refinar escopo e requisitos técnicos com o usuário.
2. Coletar e verificar fontes primárias (docs, artigos, benchmarks).
3. Produzir recomendação de techstack com alternativas e trade-offs.

<!-- Conteúdo será preenchido sequencialmente pelos passos do workflow -->

## Recomendação resumida de Techstack

- **Linguagem:** Python 3.11+ (amplo suporte de bibliotecas científicas)
- **ETL / Processamento:** pandas (>=3.0) + numpy
- **Coleta de preços:** `yfinance` (para Yahoo) e `pandas-datareader` como alternativa
- **Armazenamento:** SQLite como persistência local; camada de acesso via SQLAlchemy
- **Otimização de carteiras:** PyPortfolioOpt (alto nível) + CVXPY/OSQP ou `scipy.optimize` quando adequado
- **App / Visualização:** Streamlit para protótipos interativos; Plotly/Matplotlib para gráficos
- **Notebooks & Docs:** Jupyter + Markdown; exemplos reproduzíveis em `docs/` e `notebooks/`

## Arquitetura proposta (mínima)

- Coleta: scripts em `src/dados_b3.py` usando `yfinance`/`pandas-datareader` para obter OHLCV
- Persistência: escrever em tabela `prices(ticker, date, open, high, low, close, adj_close, volume)` no arquivo `dados/data.db` (SQLite)
- ETL: processar `adj_close` para cálculo de retornos e gravar em `returns(ticker, date, return)`
- Cálculos: usar `src/retorno.py` para funções de volatilidade, correlação e matrizes de covariância
- Otimização: camada que consome DataFrame de retornos e chama PyPortfolioOpt/CVXPY
- Visualização: notebooks e um app Streamlit que lê do SQLite e exibe resultados e fronteira eficiente

## Comandos de instalação (exemplo)

```bash
python -m pip install "pandas>=3.0" numpy yfinance pandas-datareader sqlalchemy pyportfolioopt cvxpy scipy streamlit plotly
```

## Exemplos de uso (trechos)

- Baixar preços com `yfinance` e salvar em SQLite (esboço):

```python
import yfinance as yf
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine('sqlite:///dados/data.db')
df = yf.download('PETR4.SA', start='2020-01-01', end='2023-12-31')
df.to_sql('prices', engine, if_exists='append', index_label='date')
```

- Calcular retornos diários com `pandas`:

```python
df = pd.read_sql_table('prices', engine, index_col='date', parse_dates=['date'])
returns = df['Adj Close'].pct_change().dropna()
returns.to_sql('returns', engine, if_exists='append', index_label='date')
```

## Trade-offs e riscos

- `yfinance`/Yahoo: gratuito e conveniente para protótipos e fins educacionais, mas sujeito a mudanças de API e termos de uso — não recomendado como única fonte em ambientes de produção sem revisão legal.
- SQLite: ótimo para portabilidade e simplicidade local; se precisar de concorrência ou escala, migrar para PostgreSQL ou outro RDBMS.
- PyPortfolioOpt facilita implementação da fronteira eficiente; para problemas com restrições complexas e desempenho, usar CVXPY com solver apropriado (OSQP/HiGHS).

## Recomendações operacionais

- Manter separação clara entre coleta (scripts), persistência (db), processamento (ETL) e apresentação (notebooks/app).
- Incluir testes básicos que validem: integridade de datas, ausência de duplicatas, e consistência entre `Adj Close` e retornos.
- Documentar limitações das fontes e adicionar estratégia de fallback (export CSV local quando API falhar).

## Referências e leituras verificadas

- pandas docs: https://pandas.pydata.org/docs/
- yfinance (GitHub): https://github.com/ranaroussi/yfinance
- pandas-datareader: https://pandas-datareader.readthedocs.io/
- SQLite docs: https://www.sqlite.org/docs.html
- SQLAlchemy docs: https://docs.sqlalchemy.org/
- PyPortfolioOpt: https://pyportfolioopt.readthedocs.io/
- CVXPY: https://www.cvxpy.org/
- SciPy optimize: https://docs.scipy.org/doc/scipy/reference/optimize.html
- Streamlit docs: https://docs.streamlit.io/

---

## Provedores gratuitos (sem scraping) — comparativo e snippets

A seguir 3 opções práticas para obter dados do mercado brasileiro e macroeconômicos, sem recorrer a scraping.

- **Twelve Data**
	- Prós: cobertura ampla, suporte a WebSocket, SDKs oficiais (Python), endpoints padronizados, bom para séries intraday e historic.
	- Contras: plano gratuito com limites de chamadas; verificar cobertura para alguns tickers B3 (usar sufixo e/ou mapeamento quando necessário).
	- Snippet (Python, requer `pip install twelvedata`):

```python
from twelvedata import TDClient
td = TDClient(apikey="YOUR_API_KEY")
ts = td.time_series(symbol="PETR4.SA", interval="1day", start_date="2020-01-01", end_date="2023-12-31")
df = ts.as_pandas()
print(df.head())
```

- **Alpha Vantage**
	- Prós: chave API gratuita, endpoints para séries históricas e indicadores técnicos; comunidade ampla.
	- Contras: limites de taxa relativamente baixos no plano gratuito; mapeamento de símbolos pode ser necessário para `.SA`.
	- Snippet (requests / JSON):

```python
import requests
API_KEY = "YOUR_API_KEY"
url = "https://www.alphavantage.co/query"
params = {
		"function": "TIME_SERIES_DAILY_ADJUSTED",
		"symbol": "PETR4.SA",
		"outputsize": "full",
		"apikey": API_KEY,
}
resp = requests.get(url, params=params)
data = resp.json()
# converter para DataFrame conforme a estrutura retornada
```

- **Yahoo Finance (yfinance)**
	- Prós: acesso fácil a séries históricas e `Adj Close`, amplamente usado em projetos educacionais; não requer API key.
	- Contras: dependência de endpoints públicos do Yahoo; pode sofrer alterações e limites implícitos; revisar termos de uso para produção.
	- Snippet (Python, `pip install yfinance`):

```python
import yfinance as yf
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine('sqlite:///dados/data.db')
ticker = 'PETR4.SA'
df = yf.download(ticker, start='2020-01-01', end='2023-12-31')
df.to_sql('prices', engine, if_exists='append', index_label='date')
```


- **Fontes oficiais brasileiras (Banco Central - SGS, IPEAdata, IBGE/SIDRA)** — recomendado para Selic, inflação (IPCA), séries macro
	- Prós: dados oficiais e atualizados; sem custos; adequado para séries macroeconômicas (SELIC, IPCA, desemprego, PIB trimestral).
	- Contras: nem sempre possuem cotações diárias de ações; foco em indicadores oficiais, portanto combinar com um provedor de mercado para preços.
	- Snippet (Banco Central — endpoint público):

```python
import requests
BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{format}/{series_id}/dados"
params = {"formato": "json", "dataInicial": "2020-01-01", "dataFinal": "2023-12-31"}
url = BASE.format(format="json", series_id="<SERIES_ID_SGS>")
resp = requests.get(url, params=params)
data = resp.json()
# cada item normalmente tem 'data' e 'valor' — converter para DataFrame
```

	- Notas: buscar séries relevantes (SELIC, IPCA, IGP-M, etc.) via a documentação do SGS; IPEA também fornece API para séries adicionais. Esses endpoints não exigem API key.

## Como integrar (fluxo recomendado)

1. Usar um provedor de mercado (Twelve Data ou Alpha Vantage) como fonte primária de preços OHLCV.
2. Persistir raw data no SQLite (`prices` table) com metadados da fonte e timestamp de ingestão.
3. Consultar Bacen/IPEA para séries macro (SELIC, IPCA) e armazenar em tabela `macro(series, date, value, source)`.
4. Construir ETL que junte preços e indicadores macro por período para análises (ex.: desenhar séries reais ajustadas por inflação, calcular retornos reais).

## Três melhores opções (resumo)

1. **Twelve Data** — melhor combinação de cobertura, SDK e suporte a streaming para protótipos educacionais que exigem preço intraday/historic.
2. **Alpha Vantage** — alternativa confiável com plano gratuito e endpoints amplos; bom para fallback e indicadores técnicos.
3. **Fontes oficiais brasileiras (Bacen SGS + IPEA + IBGE/SIDRA)** — indispensáveis para macroeconômicos (SELIC, IPCA). Combine com um dos provedores de preços para solução completa.

---

## Limites de API e boas práticas

- **Twelve Data**: oferece um plano `Basic` gratuito com créditos limitados (ex.: 8 API credits — ~800 chamadas/dia no nível free trial indicado na página de pricing). Para projetos educacionais, o plano gratuito costuma ser suficiente para baixas frequências; verifique a página de pricing para detalhes atualizados. Use caching, batch endpoints quando disponível e WebSocket para streaming quando necessário.
- **Alpha Vantage**: chave gratuita disponível; plano free tem limites que afetam chamadas por minuto e por dia — sempre implementar delays/exponential backoff e caching. Consulte a documentação/FAQ da Alpha Vantage para cotas atuais.
- **Yahoo (yfinance)**: não requer API key; é prático para históricos e `Adj Close`. Não há SLA e o serviço pode sofrer alterações sem aviso — trate como fonte não-SLA: armazene dados brutos e use fallback.
- **Bacen / IPEA / IBGE**: APIs oficiais geralmente não exigem chave e permitem downloads massivos de séries; respeite limites de uso e politicas do provedor (normalmente permissivas para dados oficiais).

Melhores práticas gerais:
- Implementar cache local (SQLite, arquivos Parquet) para reduzir chamadas repetidas.
- Agendar ingestões off-peak e usar backoff exponencial para erros 429/5xx.
- Registrar `source`, `fetched_at` e `raw_response` (quando aplicável) para auditoria e reprocessamento.

## Exemplos completos: ingestão para PETR4.SA e VALE3.SA e persistência

Exemplo 1 — Twelve Data (batch) → requer `pip install twelvedata`:

```python
from twelvedata import TDClient
from sqlalchemy import create_engine
import pandas as pd

td = TDClient(apikey="YOUR_API_KEY")
engine = create_engine('sqlite:///dados/data.db')

tickers = ["PETR4.SA", "VALE3.SA"]
for t in tickers:
	ts = td.time_series(symbol=t, interval="1day", start_date="2020-01-01", end_date="2023-12-31")
	df = ts.as_pandas()
	df.index = pd.to_datetime(df.index)
	df['ticker'] = t
	df.to_sql('prices', engine, if_exists='append', index_label='date')
```

Exemplo 2 — Alpha Vantage (requests) → trate limits e paginacao:

```python
import requests
import pandas as pd
from sqlalchemy import create_engine

API_KEY = "YOUR_API_KEY"
engine = create_engine('sqlite:///dados/data.db')
tickers = ["PETR4.SA", "VALE3.SA"]
for sym in tickers:
	url = "https://www.alphavantage.co/query"
	params = {"function": "TIME_SERIES_DAILY_ADJUSTED", "symbol": sym, "outputsize": "full", "apikey": API_KEY}
	resp = requests.get(url, params=params)
	j = resp.json()
	# converter j para DataFrame (ver docs AlphaVantage para estrutura exata)
	# exemplo simplificado:
	data = j.get('Time Series (Daily)', {})
	df = pd.DataFrame.from_dict(data, orient='index').rename(columns=lambda c: c.split(' ')[1])
	df.index = pd.to_datetime(df.index)
	df['ticker'] = sym
	df.to_sql('prices', engine, if_exists='append', index_label='date')
```

Exemplo 3 — Yahoo (yfinance) — simples e robusto para históricos:

```python
import yfinance as yf
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine('sqlite:///dados/data.db')
tickers = ['PETR4.SA','VALE3.SA']
df = yf.download(tickers, start='2020-01-01', end='2023-12-31', group_by='ticker')
for t in tickers:
	sub = df[t].copy()
	sub['ticker'] = t
	sub.to_sql('prices', engine, if_exists='append', index_label='date')
```

## Unindo preços com séries macro (ex.: SELIC, IPCA)

Fluxo recomendado:
- Baixe séries macro do Bacen (SGS) ou IPEA e armazene em tabela `macro(series, date, value, source)`.
- Normalize periodicidade: preços diários → agregue para mensal (ou usar fechamento mensal) para casar com índices macro que usualmente são mensais.
- Calcule retornos nominais e reais.

Exemplo de junção (pandas):

```python
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine('sqlite:///dados/data.db')
# ler preços diários e selecionar 'Adj Close'
prices = pd.read_sql_table('prices', engine, parse_dates=['date'], index_col='date')
adj = prices.reset_index().pivot(index='date', columns='ticker', values='Adj Close')
# converter para mensal (fechamento do mês)
monthly = adj.resample('M').last()
# calcular retornos mensais
returns = monthly.pct_change().dropna()

# ler macro (ex.: IPCA mensal)
macro = pd.read_sql_table('macro', engine, parse_dates=['date'], index_col='date')
ipca = macro[macro['series']=='IPCA']['value'].resample('M').last().pct_change().dropna()

# juntar returns com inflação (alinhando índices)
df = returns.join(ipca.rename('ipca'), how='inner')
# calcular retorno real aproximado (1+rn)/(1+inf)-1
for col in returns.columns:
	df[f'{col}_real'] = (1+df[col]) / (1+df['ipca']) - 1

print(df[[f'PETR4.SA_real','VALE3.SA_real']].head())
```

## Fontes e onde checar limites atualizados
- Twelve Data pricing: https://twelvedata.com/pricing
- Alpha Vantage docs/pricing: https://www.alphavantage.co/
- yfinance: https://github.com/ranaroussi/yfinance
- Bacen SGS: https://www3.bcb.gov.br/sgspub/localizarseries/localizarSeries.do?method=prepararTelaLocalizarSeries (ou API docs do SGS)

---

## Conclusão — workflow `technical-research` concluído

Status: Concluído. Este workflow produziu um relatório de pesquisa com:
- Comparativo de provedores de dados (Twelve Data, Alpha Vantage, Yahoo/yfinance, Bacen/IPEA)
- Exemplos de ingestão para `PETR4.SA` e `VALE3.SA` e snippet de persistência em SQLite
- Recomendação de techstack, arquitetura mínima e trade-offs
- Seções práticas sobre: `PyPortfolioOpt`, `Streamlit` + `Jupyter`, `Docker` (local), `python-dotenv`, `pytest`

Artefatos gerados:
- [docs/planning-artifacts/research/technical-techstack-implementacao-b3-research-2026-02-15.md]
- Backlog inicial: [docs/planning-artifacts/backlog.md]
- Brainstorming: [docs/brainstorming/brainstorming-report-20260215-1741.md]

## Stacks e ferramentas adicionais (resumo prático)

### PyPortfolioOpt
- O que é: biblioteca Python de alto nível para otimização de carteiras (mean-variance, Black-Litterman, HRP, shrinkage, discrete allocation).
- Por que usar: abstrai a matemática da otimização, ideal para POCs e material didático; integra cálculo de retornos e matrizes de risco.
- Instalação: `pip install PyPortfolioOpt`
- Snippet de uso (resumo):

```python
from pypfopt import expected_returns, risk_models, EfficientFrontier
mu = expected_returns.mean_historical_return(price_df)
S = risk_models.sample_cov(price_df)
ef = EfficientFrontier(mu, S)
weights = ef.max_sharpe()
```
- Integração: `src/portfolio.py` deve encapsular chamadas para PyPortfolioOpt e expor funções para Streamlit/notebooks.

### Streamlit + Jupyter Notebook
- O que são: Streamlit = framework leve para apps de dados; Jupyter = ambiente interativo para notebooks pedagógicos.
- Por que usar: Streamlit fornece POC interativo (arrastar/selecionar tickers, gerar fronteira eficiente); notebooks documentam passo a passo para aprendizado.
- Instalação: `pip install streamlit jupyterlab`
- Boa prática: manter notebooks em `notebooks/` e criar um `app.py` em `src/` que consome `src/*` para evitar duplicação de lógica.
- Exemplo run: `streamlit run src/app.py` e `jupyter lab notebooks/portfolio_demo.ipynb`.

### Docker (local)
- O que é: empacotamento do ambiente em container para reproduzibilidade (imagem com Python, deps, e volumes montados para `dados/`).
- Por que usar: garante que alunos/leitores rodem o POC com mesma versão das libs; facilita deploy local para testes.
- Arquivo mínimo `Dockerfile` (exemplo):

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml requirements.txt ./
RUN pip install -r requirements.txt
COPY . .
CMD ["streamlit", "run", "src/app.py"]
```
- Recomenda-se montar `dados/` como volume: `docker run -v $(pwd)/dados:/app/dados imagename`.

### python-dotenv
- O que é: leitura de variáveis de ambiente a partir de arquivo `.env` em desenvolvimento.
- Por que usar: mantém chaves/credenciais fora do código e facilita instruções para novos contribuintes.
- Instalação: `pip install python-dotenv`
- Exemplo de uso:

```python
from dotenv import load_dotenv
import os
load_dotenv()
API_KEY = os.getenv('TWELVEDATA_API_KEY')
```
- Prática: incluir `.env.example` com nomes de variáveis e instruções no README; nunca commitar `.env` real.

### pytest
- O que é: framework de testes para Python, simples e extensível.
- Por que usar: automatizar testes unitários e de integração para ETL, conectores e módulos de cálculo.
- Instalação: `pip install pytest`
- Sugestão de estrutura: `tests/test_dados_b3.py`, `tests/test_retorno.py` com fixtures que carregam pequenos CSVs de sample.
- Exemplo de comando: `pytest -q` em CI (GitHub Actions) para validar mudanças antes do merge.

---

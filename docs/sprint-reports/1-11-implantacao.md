# Implantação Story 1-11 — Definir esquema canônico de dados

Visão geral

Este documento descreve o que foi entregue na story 1-11, decisões de projeto relevantes, como validar e reproduzir os artefatos e recomendações para adoção em projetos futuros. Serve como referência técnica e operacional.

Meta da story

- Definir e documentar o esquema canônico de dados utilizado pelo projeto (columns, tipos, semantic), adicionar exemplos e garantir testes que validem a conformidade dos arquivos de amostra.

Autores e referências

- Autor principal: phbr
- Branch/commits relevantes: 514f81b, 76531bb, e4c27c6, 7407914, 991db12
- Artefatos e testes estão no repositório (veja lista abaixo).

O que foi entregue

- docs/schema.yaml — arquivo contendo o esquema canônico (ATENÇÃO: o conteúdo é JSON serializado dentro deste arquivo para compatibilidade com json.loads() nos testes).
- docs/schema.md — documentação legível explicando cada campo, versionamento do schema e políticas de migração.
- dados/examples/ticker_example.csv — exemplo canônico usado pelos consumidores e pelos testes.
- scripts/pull_sample.py — utilitário para puxar amostras do Yahoo (usa yfinance preferencialmente) e gerar CSV canônico; salva também os dados brutos do provedor em dados/examples/{TICKER}_raw.csv e {TICKER}_raw.pkl para inspeção.
- src/adapters/ — implementação de adapter (Adapter interface, AdapterError e YFinanceAdapter) para isolar provedores.
- tests/test_schema.py — valida que o exemplo corresponde ao esquema (ordem das colunas e formatos essenciais).
- tests/test_adapters.py — testes unitários para o adaptador (usa fixtures e mocks para evitar rede).

Como validar localmente

1. Instalar dependências e rodar testes unitários:

   poetry install
   poetry run pytest -q

2. Rodar apenas o teste de schema:

   poetry run pytest tests/test_schema.py -q

3. Gerar e inspecionar uma amostra bruta (exemplo):

   prun scripts/pull_sample.py PETR4.SA --days 5

   Depois, inspecionar os dados brutos em Python:

   import pandas as pd
   df = pd.read_pickle('dados/examples/PETR4.SA_raw.pkl')
   print(df.info())
   print(df.head())

Observações sobre o formato dos dados brutos

- O DataFrame bruto normalmente vem com índice de datas (DatetimeIndex) e colunas como: "Open", "High", "Low", "Close", "Adj Close", "Volume". Alguns provedores podem incluir colunas adicionais (p.ex. "Dividends", "Stock Splits").
- O script salva o bruto sem modificações, exceto garantir que exista uma coluna "Date" (faz reset_index() quando necessário) — a conversão para o esquema canônico ocorre separadamente.

Decisões de projeto e rationale

- Adapter pattern: foi criado um Adapter (src/adapters) para isolar a lógica de obtenção de cotações do restante do código — facilita trocar provedores (yfinance, pandas-datareader, etc.) sem espalhar dependências.
- Preferência por yfinance: para evitar problemas com distutils em algumas distribuições Python e reduzir dependências de sistema, as rotinas preferem yfinance quando disponível. O adaptador normaliza colunas e adiciona metadados (source, fetched_at em UTC ISO8601).
- Metadados: usamos df.attrs['source'] e df.attrs['fetched_at'] no adaptador; ao persistir no CSV canônico adicionamos as colunas: ticker, date, open, high, low, close, adj_close, volume, source, fetched_at, raw_checksum.

Arquivos importantes (resumo)

- docs/schema.yaml — esquema canônico (conteúdo JSON)
- docs/schema.md — documentação humana do schema
- dados/examples/*.csv, *_raw.csv, *_raw.pkl — exemplos e fontes brutas
- scripts/pull_sample.py — utilitário para coleta de amostras e inspeção bruta
- src/adapters/* — implementação do adapter e tratamento de erros
- tests/test_schema.py, tests/test_adapters.py — testes de validação

Recomendações e próximos passos

- Incluir validação formal de schema em CI (pandera ou validação customizada) para snapshots produzidos pelo pipeline.
- Mover o schema para um arquivo com extensão explícita (docs/schema.json) para clareza, se aceitável; atualmente mantemos JSON dentro de docs/schema.yaml para compatibilidade com testes existentes.
- Considerar adicionar um passo CI que execute scripts/pull_sample.py em modo mock para garantir que mudanças no provedor não quebrem o mapeamento.
- Documentar procedimento de atualização de dependências (adicionar yfinance ao pyproject.toml e remover pandas-datareader caso se opte por yfinance-only).

Observações finais

Este relatório foi preparado para servir como referência técnica do que foi entregue na story 1-11 e como guia para replicação/adoção das mesmas práticas em novos projetos. Para dúvidas ou histórico de decisões mais detalhado, consulte os commits listados acima e os artefatos em docs/implementation-artifacts/.

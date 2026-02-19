---
project_name: Analise-financeira-B3
date: 2026-02-15
author: Phbr
stepsCompleted:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
inputDocuments:
  - docs/brainstorming/brainstorming-report-20260215-1741.md
  - docs/brainstorming/brainstorming-session-20260215-145405.md
  - docs/planning-artifacts/research/technical-techstack-implementacao-b3-research-2026-02-15.md
  - docs/planning-artifacts/backlog.md
---

# Product Brief: Analise-financeira-B3

## Executive Summary

Analise-financeira-B3 é um laboratório pessoal reprodutível para experimentação com dados da B3. Inclui scripts modulares de ingestão, persistência em SQLite (fonte canônica), pipelines ETL testáveis para cálculo de retornos e métricas, notebooks passo‑a‑passo e visualizações interativas para comparar pipelines e acompanhar experimentos ao longo do tempo. Toda documentação está em PT‑BR com foco em reprodutibilidade, clareza e facilidade de iterar em abordagens alternativas (CSV vs SQLite). O repositório adotará SQLite como fonte canônica (tabelas `prices` e `returns`), com scripts para exportação/snapshots em CSV para intercâmbio e inspeção.

---

## Core Vision

### Problem Statement

Não existe um espaço pessoal centralizado e reprodutível em PT‑BR que documente, passo a passo, como coletar, tratar e analisar dados da B3 com exemplos executáveis e critérios de aceitação claros.

### Problem Impact

Sem esse repositório pessoal, o aprendizado fica fragmentado, experimentos não são facilmente reproduzidos e o histórico de decisões e resultados se perde.

### Why Existing Solutions Fall Short

Soluções existentes tendem a ser orientadas a públicos externos ou comerciais, fragmentadas, e sem foco em preservar o histórico de experimentos ou permitir comparação direta entre abordagens técnicas.

### Proposed Solution

Criar um repositório end‑to‑end que centralize conhecimento e experimentos, permitindo comparar abordagens (CSV vs SQLite) e preservar histórico de testes. Componentes principais:
- Módulos: Coleta & Ingestão, Processamento & ETL, Cálculos Estatísticos, Modelos de Carteira, Visualização & Relatórios, Documentação & Experimentos;
- Persistência padronizada (SQLite com esquema definido) e scripts para exportação/snapshots em CSV;
- Notebooks e scripts executáveis para reproduzir análises e comparar pipelines;
- Visualizações interativas (ex.: Streamlit para dashboards interativos; Plotly/Altair para visualizações) para explorar resultados e validar escolhas de processamento e apresentação;
- Documentação em PT‑BR, checklist de experimentos, e scripts de reproducibilidade (Docker/CI), além de checkpoints para registrar versões experimentais;
- Backlog com issues e critérios de aceitação para cada tarefa.

### Key Differentiators

- Laboratório pessoal focado em aprendizado e experimentação contínua;
- Visualizações cujo objetivo é ajudar a entender e escolher formas de processar e apresentar os dados;
- Ferramentas e formatos que facilitam comparação direta entre pipelines (CSV, SQLite);
- Documentação em PT‑BR com notas detalhadas de experimentos e instruções reproduzíveis.

### Success Criteria (mensuráveis)

- Scripts de ingestão capazes de baixar PETR4.SA e VALE3.SA e persistir em dados/data.db;
- Tabelas `prices` e `returns` populadas e documentadas;
- Notebooks executáveis que reproduzem análises e gráficos;
- README com quickstart e comando para rodar o app POC.

## MVP Scope

### Core Features (Mínimo Viável)
- Ingestão confiável e idempotente
  - Jobs de ingestão por ticker com retries/backoff, logs e status (`ingest_logs`).
  - Execução via CLI e/ou agendamento local (cron), com testes automatizados e checks de integridade.
- Esquema canônico SQLite mínimo
  - Tabelas: `prices(ticker, date, open, high, low, close, adj_close, volume, source)` e `returns(ticker, date, return_type, return_value)`.
  - Helpers: `db.write_prices`, `db.read_prices`, `db.append_prices`.
- Snapshots CSV & verificação
  - Script para produzir snapshots CSV por experimento (timestamped) e rotina de verificação (checksums/rowcounts) para auditabilidade.
- Notebook quickstart reprodutível
  - Notebook de exemplo (PETR4.SA / VALE3.SA) que executa ingest → popula SQLite → gera gráfico comparativo.
  - Instruções step‑by‑step no README para executar em ambiente limpo.
- POC Streamlit (visualização interativa)
  - App POC que carrega dados do SQLite e apresenta visualizações comparativas (OHLC, retornos, comparação de pipelines).
  - Comando de execução simples (ex.: `poetry run streamlit run src/apps/poc_streamlit.py`).
- Infra e observabilidade mínimas
  - Tabelas de logs (`ingest_logs`, `runs`, `experiments`), testes básicos e scripts de snapshot para reproduzibilidade.

### Out of Scope (para MVP)
- Parquet/formatos de dataset complexos (removido conforme solicitado)
- Orquestração distribuída (Airflow/Kubernetes), pipelines streaming, e otimizações de performance em escala
- UI completa além do POC Streamlit (dashboards avançados ficam para v2)
- Modelos de otimização de portfólio complexos e integrações comerciais

### Critérios de Sucesso do MVP
- Dados são puxados e armazenados no banco de dados de forma correta
- Snapshot CSV gerado e verificado para pelo menos 2 experimentos (PETR4.SA, VALE3.SA).
- Streamlit POC funciona localmente e mostra dados carregados do DB para os tickers de exemplo.

### Future Vision (v2+)
- CI/CD para testes e snapshots automáticos; agendamento robusto de ingestões; dashboards avançados e comparativos multi-ticker; módulos de análise de carteira; benchmarking de implementações.
## Target Users

### Primary Users

#### Lucas — Pesquisador / Estudante de Finanças
- Nome & contexto: Lucas, 26, mestrando em Finanças; utiliza notebooks Jupyter para reproduzir estudos acadêmicos e testar hipóteses de mercado. Trabalha com séries históricas e precisa de pipelines reprodutíveis e rastreáveis para comparar métodos de cálculo de retorno.
- Como experiencia o problema: dados dispersos entre fontes, ajustes por dividendos e splits inconsistentes, e falta de registros de experimentos que expliquem diferenças entre runs.
- Visão de sucesso: consegue executar um notebook que reproduz exatamente um experimento, com dados persistidos em SQLite e snapshots CSV, e documenta cada parâmetro e etapa.

#### Mariana — Investidora Pessoa Física
- Nome & contexto: Mariana, 34, investidora individual que acompanha carteiras no tempo livre. Usa planilhas e tutoriais online para avaliar ações e quer uma forma confiável de comparar metodologias (ex.: retorno simples vs. returns ajustados).
- Como experiencia o problema: dificuldade em validar resultados entre diferentes fontes/metodologias; precisa de passos claros para reproduzir análises sem ambiguidade.
- Visão de sucesso: tem um quickstart e notebooks que permitem verificar resultados (ex.: PETR4.SA) e entender diferenças entre pipelines de forma prática.

#### Rafael — Analista / Engenheiro de Dados
- Nome & contexto: Rafael, 30, engenheiro de dados freelance responsável por montar pipelines e integrar dados para projetos analíticos. Prefere código modular, testes automatizados e esquemas de dados bem definidos.
- Como experiencia o problema: scripts ad-hoc sem padrão, falta de esquema canônico e dificuldade em versionar snapshots de dados para auditoria.
- Visão de sucesso: encontra um esquema SQLite claro (`prices`, `returns`), helpers para leitura/gravação, e scripts de snapshot/CSV que permitem auditoria e integração em pipelines CI.

### Secondary Users

- Helena — Mentor/Professor: revisa experimentos e dá feedback metodológico; usa o repositório para demonstrar boas práticas a alunos.
- Futuro 'eu' / Arquivista de Experimentos: pessoa que retorna ao repositório meses depois para entender decisões, reexecutar experimentos e comparar resultados.

### User Journey

- Discovery: encontra o repositório via referência em anotações pessoais, link em um notebook ou por busca no GitHub.
- Onboarding: segue o README quickstart (instala dependências, executa exemplo com PETR4.SA) e executa o notebook de exemplo para confirmar ambiente.
- Core Usage: executa scripts de ingestão, carrega dados de `prices` no banco SQLite, roda notebooks que reproduzem cálculos de retorno e gera visualizações comparativas.
- Success Moment (Aha!): reproduz um gráfico/resultado idêntico a um experimento anterior usando snapshots CSV + banco SQLite e entende por que duas abordagens deram resultados distintos.
- Long-term: usa o repositório para comparar abordagens, versionar experimentos e compartilhar trechos de código/testes com colegas.

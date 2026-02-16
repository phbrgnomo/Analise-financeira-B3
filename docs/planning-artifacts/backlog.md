# Backlog Inicial — Analise-financeira-B3

Descrição: backlog inicial organizado por módulo, com etiquetas e estimativas para orientar implementação e criação de issues.

## Módulos e Tarefas Prioritárias

- [ ] Coleta & Ingestão — Implementar download via pandas-datareader (.SA), salvar CSVs em dados/ (labels: enhancement, backend) — Estimativa: 3 SP
- [ ] Coleta & Ingestão — Cache e atualização incremental (labels: enhancement) — Estimativa: 2 SP
- [ ] Processamento & ETL — Ajuste por proventos e cálculo de retornos (gerar retornos/<TICKER>_returns.csv) (labels: data-processing) — Estimativa: 5 SP
- [ ] Processamento & ETL — Normalização de colunas e tratamento de missing (labels: data-processing, bug) — Estimativa: 3 SP
- [ ] Cálculos Estatísticos — Implementar funções: média, variância, volatilidade anualizada, correlação, covariância (labels: math, analysis) — Estimativa: 5 SP
- [ ] Cálculos Estatísticos — Visualizações (heatmap, pairplot) e notebooks demonstrativos (labels: viz, docs) — Estimativa: 3 SP
- [ ] Modelos de Carteira — Fronteira eficiente (Markowitz) e plotagem (labels: modeling) — Estimativa: 8 SP
- [ ] Modelos de Carteira — CAPM: calcular beta/alpha vs índice proxy (labels: modeling, analysis) — Estimativa: 3 SP
- [ ] Modelos de Carteira — Prototipo Black-Litterman (labels: modeling, research) — Estimativa: 8 SP
- [ ] Visualização & Relatórios — Funções utilitárias de plot e notebooks Jupyter/Colab (labels: viz, docs) — Estimativa: 3 SP
- [ ] Visualização & Relatórios — Dashboard Interativo (Streamlit + Plotly): visualização de dados históricos/atuais, geração de carteiras modelo e projeção de volatilidade (labels: viz, docs, modeling) — Estimativa: 5 SP
- [ ] Documentação & Exemplos — Atualizar README, criar tutoriais e exercícios (labels: docs) — Estimativa: 3 SP
- [ ] Infra/CI (opcional) — Scripts de verificação básica e formatação (labels: infra, ci) — Estimativa: 2 SP

## Organização e Próximos Passos

- Converter cada item em issue no GitHub com a etiqueta apropriada e a estimativa.
- Priorizar um "sprint" inicial: foco em Coleta & Ingestão + Processamento & ETL + Cálculos Estatísticos (soma estimada ~13 SP).
- Criar notebooks de exemplo para PETR4.SA e VALE3.SA como artefatos de demonstração.

---

- [ ] Coleta & Ingestão — Suporte a SQLite: definir esquema e implementar funções de escrita/leitura (labels: backend, data-processing) — Estimativa: 3 SP
- [ ] Processamento & ETL — Migração/integração com SQLite: funções que geram retornos e armazenam em tabela 'returns' (labels: data-processing) — Estimativa: 3 SP
- [ ] Visualização & Relatórios — Adaptar utilitários para ler do SQLite e gerar visualizações interativas (labels: viz, docs) — Estimativa: 2 SP
- [ ] Tests — Integridade do SQLite e checks para CI (labels: infra, data-processing) — Estimativa: 2 SP — Issue: #18

Se desejar, gero as issues automaticamente (requer acesso ao GitHub CLI/autenticação) ou executo um export em formato CSV para importação de issues.

## Tarefas técnicas imediatas (recomendadas)

- [ ] Definir esquema canônico do banco SQLite (tabelas `prices`, `returns`, `snapshots`, `ingest_logs`) — labels: backend, data-model — Estimativa: 1 SP
- [ ] Implementar idempotência de ingestão (upsert por `ticker,date` ou arquitetura raw → processed) e flags `--force-refresh` — labels: backend, data-processing — Estimativa: 2 SP
- [ ] Implementar geração de snapshot CSV com checksum SHA256 e formato padrão (`snapshots/<ticker>-YYYYMMDD.csv`) — labels: backend, data-processing — Estimativa: 1 SP
- [ ] Criar teste de integração quickstart: ingesta de um ticker de amostra, validação de rows, geração de snapshot e verificação de checksum — labels: test, infra — Estimativa: 2 SP
- [ ] Documentação técnica: criar arquivos iniciais `docs/architecture.md`, `docs/data-model.md`, `docs/how-to-extend.md`, e `docs/playbooks/quickstart-ticker.md` — labels: docs, tech-writing — Estimativa: 2 SP
- [ ] Definir contrato de módulos (interfaces mínimas `db.write_prices`, `db.read_prices`, `pipeline.ingest`, `portfolio.generate`) e exemplos de uso — labels: backend, api — Estimativa: 2 SP
- [ ] Especificar critérios mensuráveis para portfólios gerados (retorno esperado, volatilidade, Sharpe) e incluir como critérios de aceitação do MVP — labels: modeling, analysis — Estimativa: 1 SP

## Próximos passos sugeridos

- Priorizar sprint inicial incluindo: Definir esquema DB, Implementar ingestão idempotente, Teste quickstart e Documentação quickstart (soma estimada ~6 SP).
- Após implementação inicial, criar testes de integração adicionais e pipelines de CI para validação automática do quickstart.

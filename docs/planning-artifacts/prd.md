---
stepsCompleted:
  - step-01-init
  - step-01b-continue
  - step-02-discovery
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-07-validated
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-12-complete
inputDocuments:
  - docs/planning-artifacts/product-brief-Analise-financeira-B3-2026-02-15.md
  - docs/planning-artifacts/research/technical-techstack-implementacao-b3-research-2026-02-15.md
  - docs/brainstorming/brainstorming-session-20260215-145405.md
  - docs/planning-artifacts/backlog.md
documentCounts:
  brief: 1
  research: 1
  brainstorming: 1
  projectDocs: 1
workflowType: 'prd'
project_name: Analise-financeira-B3
author: Phbr
date: 2026-02-15
classification:
  projectType: developer_tool
  domain: financeiro
  complexity: medium
  projectContext: brownfield
---

# Product Requirements Document - Analise-financeira-B3

**Author:** Phbr
**Date:** 2026-02-15

> Espaço inicializado pelo workflow `create-prd`.

## Executive Summary

Analise-financeira-B3 é um laboratório pessoal e reprodutível para aprender e experimentar com dados da B3. O objetivo é fornecer ferramentas, exemplos e playbooks em PT-BR que permitam a um pesquisador ou desenvolvedor executar um fluxo end‑to‑end: ingestão de preços, persistência em SQLite, cálculo de retornos e geração de visualizações e snapshots auditáveis. Público‑alvo: pesquisadores, estudantes e desenvolvedores que desejam reproduzir experimentos e comparar pipelines.

Sucesso imediato: um usuário consegue, em uma máquina de desenvolvimento, executar o quickstart e reproduzir um experimento completo (ingest → persistência → notebook → snapshot) em ≤ 30 minutos.

Escopo do documento: define requisitos funcionais e não‑funcionais, jornadas de usuário, critérios de aceitação e recomendações de implementação para um MVP educativo que prioriza reprodutibilidade e clareza.


## User Journey

### Jornada 1 — Usuário Primário (Lucas, pesquisador)
- Abertura: Lucas precisa analisar um ticker novo para um experimento pedagógico; tem ~30 minutos para reproduzir um pipeline.
- Ações: fornece `TICKER` ao quickstart (CLI/GUI) → executa ingest (download → persistência em `dados/data.db`) → roda notebook que calcula retornos e plota gráficos → gera snapshot CSV.
- Clímax: pipeline completa sem erros e o notebook gera o gráfico comparativo esperado.
- Resolução: Lucas salva snapshot e anota parâmetros do experimento; consegue iterar com outro ticker.
- Requisitos revelados:
  - CLI/GUI com input `ticker` e feedback em tempo real (logs/contagem linhas).
  - Idempotência / upsert por (ticker,date).
  - Notebooks parametrizáveis por `ticker`.
  - Export de snapshot CSV + checksum.

### Jornada 2 — Usuário Primário (Edge Case: dados faltantes / erro de fonte)
- Abertura: Usuário solicita ingest de ticker que tem lacunas ou falha temporária do provedor.
- Ações: ingest tenta, detecta gaps ou 5xx → sistema registra erro em `ingest_logs` e tenta retries/backoff; oferece opção `--use-cache` ou salvar raw CSV para diagnóstico.
- Clímax: Se retries falham, a rotina salva fallback (raw CSV) e notifica usuário com instruções de recuperação; se succeed, processo segue.
- Resolução: Usuário reexecuta com `--force-refresh` após ajuste ou aceita dados parciais com aviso.
- Requisitos revelados:
  - Estratégia de retries/backoff e flags `--force-refresh`, `--use-cache`.
  - Logs estruturados (`ingest_logs`) com contagens/erros.
  - Mecanismo de fallback (raw CSV) e documentação de recuperação.

### Jornada 3 — Admin / Operações (Manutenção e Monitoramento)
- Abertura: Administrador precisa monitorar saúde dos ingest jobs e espaço do DB, além revisar snapshots e backups.
- Ações: acessa painel/CLI de monitoramento → visualiza último ingest por ticker, latência, contagem de linhas, status de snapshot → agenda re-ingest ou limpeza de snapshots antigos → exporta backup de `dados/data.db`.
- Clímax: Detecta ingest falho recorrente; isola ticker e executa job manual com `--force-refresh` e coleta logs para análise.
- Resolução: Job succeed ou escalonamento para desenvolvedor; registros de auditoria mantidos.
- Requisitos revelados:
  - Painel/CLI operacional com métricas e histórico.
  - Rotinas de backup/retenção de snapshots.
  - Permissões mínimas e documentação de runbook.

### Jornada 4 — Consumidor de API / Desenvolvedor (Integração e Geração de Portfólio)
- Abertura: Desenvolvedor quer usar os dados coletados para gerar um portfólio programaticamente.
- Ações: chama `db.read_prices(ticker, start, end)` → obtém DataFrame → passa para `portfolio.generate(method='markowitz', params=...)` → recebe pesos, métricas (retorno esperado, volatilidade, Sharpe) → salva resultado.
- Clímax: Geração do portfólio produz métricas que atendem critérios mínimos e é exportada como artifact (CSV/JSON).
- Resolução: Desenvolvedor integra resultado ao notebook/Streamlit e documenta experimento.
- Requisitos revelados:
  - APIs/contratos de módulos (`db.*`, `pipeline.ingest`, `portfolio.generate`) com exemplos.
  - Formato padrão de saída para portfólios (pesos + métricas).
  - Testes de integração para pipeline→modelo.

### Resumo de Requisitos Derivados (alta prioridade)
- Interface CLI/GUI para quickstart com parâmetro `ticker` e flags (`--force-refresh`, `--use-cache`).
- Esquema DB e contratos de módulo (leitura/gravação + geração de portfólio).
- Logs estruturados `ingest_logs` e snapshots com checksum em `snapshots/`.
- Retentiva/backup e painel/CLI de operações.
- Notebooks parametrizáveis e documentação playbook `quickstart-ticker.md`.
- Teste de integração quickstart que valida ingest→snapshot→notebook.


## Success Criteria

### User Success
- Usuário fornece um ticker existente como entrada e executa o fluxo de ingestão (download → persistência) para esse ticker.
- Usuário consegue rodar o quickstart e reproduzir um experimento end‑to‑end (ingest → popular SQLite → notebook gera gráfico) em uma máquina dev em ≤ 30 minutos.

### Business / Project Success
- Repositório cumpre objetivo pedagógico: quaisquer exemplos (ex.: PETR4.SA, VALE3.SA) são apenas referências — o critério é suportar qualquer ticker válido fornecido pelo usuário e permitir reprodução.
- Backlog inicial implementado para MVP (ingest + returns + POC) conforme prioridades definidas.

### Technical Success
- Ingestão idempotente parametrizada por ticker (usuário informa ticker), gravando em `dados/data.db` nas tabelas `prices` e `returns`.
- Esquema mínimo esperado (exemplo):
  - `prices(ticker TEXT, date DATE, open REAL, high REAL, low REAL, close REAL, adj_close REAL, volume INTEGER, source TEXT, fetched_at DATETIME)`
  - `returns(ticker TEXT, date DATE, return_type TEXT, return_value REAL)`
- Snapshot CSVs gerados e verificados (formato CSV + checksum SHA256), salvos em `snapshots/<ticker>-YYYYMMDD.csv`.
- Streamlit POC e notebooks leem do SQLite e exibem resultados para o ticker fornecido.
- Convenção de 252 dias usada para anualizações onde aplicável.
- Documentação completa de cada etapa de implementação: descrição do funcionamento, lógica, decisões de design e conceitos por trás de cada módulo (coleta, ETL, cálculo de retornos, persistência, geração de portfólios, visualização). Deve permitir que outro desenvolvedor entenda e estenda as implementações.

### Measuráveis
- Ingestão e persistência bem-sucedidas para um ticker fornecido pelo usuário; snapshot CSV criado com checksum válido.
- `poetry run main` / `python -m src.main` realiza quickstart sem erro.
- Documentação: README + `docs/` explicando arquitetura, data-model e como estender módulos.
- Documentação para cada etapa de implementação, guardadas em `docs/implantacao/<numeração sequencial>-<o que foi implementado>.md`, contendo:
  - Descrição do objetivo da implementação
  - Soluções consideradas durante a implantação
  - Motivos para escolha da decisão implantada
  - Explicação de pontos principais da implementação com as respectivas referencias
  - Conclusões quando ao processo de implementação e descobertas relevantes
- Criação de uma carteira recomendada utilizando ativos selecionados pelo usuário (Markowitz, Black Litterman ou CAPM)

## Product Scope

### In‑Scope (MVP)
- Ingestão idempotente por ticker com adaptadores para provedores gratuitos (Yahoo, AlphaVantage/TwelveData)
- Persistência local em SQLite (`dados/data.db`) com tabelas mínimas `prices`, `returns`, `ingest_logs`, `snapshots`, `metadata`
- Geração de snapshot CSV com checksum e rotina de verificação
- Notebooks de exemplo e quickstart (comando `poetry run main --ticker ...`)
- Streamlit POC para visualização local
- Scripts e playbooks de operação (backup, restore, healthcheck)
- Ao menos uma implementação de modelagem de portifólio (a ser definido baseado em complexidade de implementação)

### Out‑Of‑Scope (para MVP)
- APIs públicas e autenticação de usuários
- Orquestração distribuída (Airflow/Kubernetes) e soluções de escala horizontal avançada
- Integrações pagas ou contratos de SLA para provedores de dados

### Phased Approach
- Phase 1 (MVP): implementação das funcionalidades In‑Scope listadas acima para suportar experimentos reprodutíveis.
- Phase 2 (Growth): adicionar suporte a múltiplos provedores, testes automatizados de integração em CI e containerização robusta.
- Phase 3 (Expansion): funcionalidades avançadas de modelagem de carteiras, dashboards públicos e orquestração.

### MVP (escopo mínimo)
- Ingestão idempotente parametrizada por ticker → grava em SQLite (`prices`, `returns`).
- Cálculo de retornos diários e persistência em `returns`.
- Notebooks de exemplo e README quickstart.
- Streamlit POC que consome `dados/data.db`.
- Geração de pelo menos 1 portfólio usando um dos modelos (ex.: Markowitz) como POC, com métricas reportadas (retorno esperado, volatilidade, Sharpe).
- Modularização clara dos componentes (coleta, ETL, cálculo, persistência, modelagem) para permitir novas implementações que consumam os dados armazenados.

---

## Domain-Specific Requirements

### Contexto
- Domínio detectado: `financeiro` (ferramenta de estudo). Requisitos regulatórios formais (KYC/AML, PCI, etc.) **não se aplicam** no escopo atual, pois não haverá clientes/produção. Aplicaremos boas práticas técnicas para garantir integridade, auditabilidade e segurança local.

### Compliance & Regulatory
- Nota: não aplicável para o escopo atual. Incluir checklist de revisão regulatória caso o projeto evolua para uso em produção.

### Technical Constraints
- **Proveniência e integridade de dados:** armazenar `source`, `fetched_at`, `raw_response` (quando aplicável) e `query_params` a cada ingest para auditabilidade.
- **Rate limits e backoff:** backoff exponencial e retries configuráveis; cache local para reduzir chamadas repetidas.
- **Segurança mínima local:** proteger `dados/data.db` com permissões (owner-only); não commitar credenciais; recomendar uso de `.env` e, se necessário, criptografia de disco/arquivo para dados sensíveis.
- **Acesso & exposição:** por padrão, não expor APIs públicas; se necessário, exigir autenticação/authorization antes de exposição.
- **Audit & observabilidade:** `ingest_logs` (ticker, started_at, finished_at, rows_fetched, status, error_message) e metadados de snapshot com checksum.
- **Performance & escala:** desenhado para ingest de 1 ticker por job; suportar batch como extensão pós-MVP.
- **Integrações de fonte:** implementar adaptadores para `yfinance`, `pandas-datareader`, `twelvedata`, `alpha_vantage`; cada adaptador registra origem e limitações.

### Integration & Data Model
- Tabelas mínimas recomendadas: `prices`, `returns`, `snapshots`, `ingest_logs`, `metadata` (schema_version, source_versions).
- Contratos públicos sugeridos: `db.write_prices(df, ticker)`, `db.read_prices(ticker, start, end)`, `pipeline.ingest(ticker, source, opts)`, `portfolio.generate(prices_df, method, params)`.

### Risk Mitigations
- **Provider downtime / API changes:** cache raw responses, salvar fallback CSV e alertar via `ingest_logs`.
- **Dados corrompidos/parciais:** validar contagens, detectar duplicatas/gaps e flagar runs fora de tolerância.
- **Crescimento do DB:** políticas de retenção de snapshots, rotinas de purge/archival e recomendações para migração a RDBMS se necessário.

### Deliverables (docs/checklist)
- `docs/data-model.md` — esquema e exemplos de queries.
- `docs/architecture.md` — fluxos de ingest, ETL, snapshot e geração de portfólio.
- `docs/playbooks/quickstart-ticker.md` — quickstart passo-a-passo para reproduzir um experimento com um ticker.
- `docs/playbooks/runbook-ops.md` — runbook de operações (backup, restore, troubleshooting de ingest).
- `docs/sprint-reports/0-3-pre-commit-implantado.md` — documento de implantação e verificação para a story 0.3 (pre-commit, black, ruff, CI).

## Project-Type Deep Dive (Step 07)

### Overview
- Projeto classificado como `developer_tool` — foco em APIs, contratos de módulo e documentação de desenvolvedor.
- Objetivo do Step 07: traduzir escolhas de implementação em requisitos técnicos acionáveis e lista de artefatos de documentação.

### Implementação — decisões do usuário
- Linguagem: Python 3.12
- Gerenciador de pacotes/build: poetry
- IDE preferida: VSCode
- Banco de dados: SQLite

### Formato de documentação
- Formato escolhido: Markdown (todos os documentos e playbooks serão escritos em Markdown em `docs/`).
- Observação: exemplos/artefatos de referência (código, notebooks, exemplos de SDK) serão adicionados ao repositório posteriormente conforme indicado.

### Requisitos específicos para `developer_tool`
- `Public API/Module Contracts`: documentar assinaturas e exemplos para `db.write_prices`, `db.read_prices`, `pipeline.ingest`, `portfolio.generate`.
- `Quickstart & Playbooks`: `docs/playbooks/quickstart-ticker.md` em Markdown, com comando `poetry run main` e exemplos de `ticker`.
- `Data model`: `docs/data-model.md` descrevendo tabelas `prices`, `returns`, `snapshots`, `ingest_logs`, `metadata` com exemplos de queries.
- `Architecture`: `docs/architecture.md` descrevendo fluxo ingest→ETL→persistência→consumo (notebooks/Streamlit/portfólio).
- `Testing`: testes unitários para adaptadores de fonte; integração end-to-end que executa ingest→snapshot→notebook; recomenda-se `pytest` com fixture de SQLite temporário.
- `Packaging`: instruções para publicar pacote localmente (`poetry build`, `poetry install`, `poetry run`).
- `CI`: pipeline mínimo para `push`/`merge` que roda `poetry install`, `pytest`, linter (opcional) e checa formatação Markdown/links.


### API Contracts (exemplos)
- `db.write_prices(df: pandas.DataFrame, ticker: str) -> None` — grava/atualiza registros na tabela `prices` (idempotente por (ticker,date)).
- `db.read_prices(ticker: str, start: Optional[str]=None, end: Optional[str]=None) -> pandas.DataFrame` — retorna preços filtrados por intervalo.
- `pipeline.ingest(ticker: str, source: str='yfinance', force_refresh: bool=False, use_cache: bool=True) -> str` — executa ingest e retorna caminho do snapshot CSV gerado.
- `portfolio.generate(prices_df: pandas.DataFrame, method: str='markowitz', params: dict=None) -> dict` — retorna `{'weights': {...}, 'expected_return': float, 'volatility': float, 'sharpe': float}`.

Exemplo de uso CLI quickstart:

```
poetry run main --ticker PETR4.SA --force-refresh
```

### Testing & CI
- Testes unitários: usar `pytest` com fixtures que criam um SQLite em memória/temporário para testar `db.*` e adaptadores de fonte.
- Teste de integração (end-to-end): rotina que executa `pipeline.ingest` para um `ticker` de exemplo (mockando chamadas à API em CI) e verifica que o snapshot CSV existe e checksum SHA256 confere com o gerado.
- CI pipeline mínimo: 1) `poetry install --no-dev` 2) `poetry run pytest -q` 3) checagem de links/formatos Markdown (opcional: `markdown-link-check`) 4) (opcional) linter/formatador (`ruff`/`black`).

## Non-Functional Requirements (Detalhado)

### Performance
- NFR-P1: Quickstart end‑to‑end (`poetry run main --ticker <TICKER> --force-refresh`) completa em ≤ 30 minutos em máquina dev típica.
- NFR-P2: Comando de healthcheck/metrics responde em < 5s sob carga normal (ex.: sem ingest concorrente pesado).
- NFR-P3: Geração de snapshot CSV para um ticker com até 10 anos de dados diários conclui em < 2 minutos em máquina dev típica.

### Confiabilidade / Resiliência
- NFR-R1: Ingests falhos executam retry exponencial com até 3 tentativas documentadas; falhas são registradas em `ingest_logs` com motivo.
- NFR-R2: Backups de `dados/data.db` podem ser feitos manualmente e agendados; rotina de restauração deve ser testada regularmente.

### Observabilidade
- NFR-O1: Sistema exporta logs estruturados (JSON) com campos mínimos: `ticker`, `job_id`, `started_at`, `finished_at`, `rows_fetched`, `status`, `error_message`, `duration_ms`.
- NFR-O2: Métricas básicas (jobs por ticker, latência média, taxa de erro por fonte) estão disponíveis via comando `main --metrics`.

### Concorrência / Escalabilidade
- NFR-S1: O sistema garante execução concorrente segura por ticker (um job por ticker por vez); tentativas concorrentes são enfileiradas ou rejeitadas e logadas.
- NFR-S2: Projeto deve permitir extensão para batch/multi‑ticker sem comprometer integridade do SQLite (documentado como limite operacional).

### Segurança Operacional
- NFR-Sec1: Por padrão, o arquivo `dados/data.db` tem permissões owner-only (ex.: `chmod 600`) após criação.
- NFR-Sec2: Chaves/segredos não são comitados; projeto fornece `.env.example` e recomenda `python-dotenv` para desenvolvimento.

### Manutenibilidade / Operações
- NFR-M1: Migrações de esquema são versionadas e suportam rollback seguro (`migrations status` / `migrations apply` / `migrations rollback`).
- NFR-M2: CI executa testes unitários e de integração, e falha se geração de CSV ou checksum estiver incorreta.

### Integração
- NFR-INT1: Adaptadores de provedores implementam interface estável e documentada com retries configuráveis e logging de rate limits.

### Acessibilidade
- Não aplicável para escopo MVP (aplicação de uso técnico/educacional local); considerar para versões públicas.

### Acceptance Curta (NFRs críticos)
- NFR-P1: quickstart completa ≤ 30 minutos (teste manual/CI spike).
- NFR-R2 / NFR-M1: backup e restore testados em ambiente de staging.
- NFR-O2: `main --metrics` exibe métricas recentes e erros agregados.


### Acceptance Criteria (mapeado)
- `quickstart_end_to_end` (automatable): executa `poetry run main --ticker <sample>` e produz snapshot CSV em `snapshots/` com checksum válido; retorno da função `pipeline.ingest` indica sucesso.
- `db_contracts` (unit): testes unitários para `db.read_prices`/`db.write_prices` que validam esquema e idempotência.
- `portfolio_poc` (integration): gera portfólio com métricas retornadas e grava resultado em formato CSV/JSON conforme contrato.

## Functional Requirements

### Ingestão de Dados
- FR1: [Usuário/CLI] pode iniciar ingest de preços para um ticker específico.
- FR2: [Sistema] pode recuperar dados de pelo menos dois provedores (Yahoo, AlphaVantage) via adaptadores.
 - FR2: [Sistema] pode recuperar dados de múltiplos provedores configuráveis via adaptadores.
- FR3: [Sistema] grava a resposta bruta do provedor em arquivo CSV em `raw/<provider>/`.
- FR4: [Sistema] inclui metadados ao persistir dados brutos (`source`, `fetched_at`, `rows`, `checksum`).
- FR5: [Usuário/CLI] pode executar um health‑check de conexão para um provedor via comando.

### Validação e Qualidade dos Dados
- FR6: [Sistema] valida a estrutura do CSV recebido contra um schema mínimo (colunas esperadas).
- FR7: [Sistema] rejeita/flag rows que não atendam ao schema e registra motivo em `ingest_logs`.
- FR8: [Usuário/CLI] pode solicitar um relatório de validação de amostra para um arquivo CSV.

### Persistência / Banco de Dados
- FR9: [Sistema] persiste dados validados no banco local (`dados/data.db`) nas tabelas mínimas (`prices`, `returns`, `ingest_logs`, `snapshots`, `metadata`).
- FR10: [Sistema] realiza upsert por (ticker, date) para evitar duplicação.
- FR11: [Desenvolvedor/API] pode ler preços por ticker e intervalo via contrato `db.read_prices(ticker, start, end)`.
- FR12: [Desenvolvedor/API] pode gravar preços via contrato `db.write_prices(df, ticker)`.

### Snapshots e Exportação
- FR13: [Sistema] gera snapshot CSV(s) a partir de dados persistidos e salva em `snapshots/` com checksum SHA256.
- FR14: [Usuário/CLI] pode exportar dados persistidos para CSV/JSON a pedido.
- FR15: [Sistema] registra metadados do snapshot (created_at, rows, checksum) em `metadata` ou `snapshots` table.

### CLI e Operações
- FR16: [Usuário/CLI] pode executar `poetry run main --ticker <TICKER> [--force-refresh]` para quickstart end‑to‑end.
- FR17: [Usuário/CLI] pode executar subcomando `--test-conn --provider <name> --health`.
- FR18: [Administrador] pode listar histórico de ingestões e status via comando operacional.

### Notebooks e Visualização
- FR19: [Usuário] pode abrir notebook parametrizável que consome `dados/data.db` para um ticker fornecido.
- FR20: [Usuário] pode executar notebook quickstart e gerar gráficos comparativos (prices/returns).
- FR21: [Sistema] fornece rotina que transforma preços em returns diários e grava em `returns`.

### Streamlit / Visual POC
- FR22: [Usuário] pode iniciar um POC Streamlit que lê do banco local e exibe gráficos básicos por ticker.
 - FR23: [Dev/Ops] pode executar POC Streamlit localmente; requisitos de implantação e containerização documentados separadamente.

### Modelagem e Portfólio
 - FR24: [Desenvolvedor/API] pode invocar `portfolio.generate(prices_df, params)` (ou equivalente) e receber pesos + métricas.
- FR25: [Sistema] exporta resultados de modelagem em CSV/JSON compatível com consumo por notebooks.

### Testes, CI e Qualidade
- FR26: [CI] executa testes unitários e integração mockada que validam ingest→CSV→checksum fluxo.
- FR27: [Desenvolvedor] pode rodar suíte de testes localmente e obter resultados pass/fail claros.

- ### Documentação e Relatórios
- FR28: [Tech Writer] pode adicionar `docs/phase-N-report.md` com checklist, comandos reproducíveis e amostras de CSV para cada fase. Pode adicionar `docs/sprint-reports/<epic>-<story>-<o que foi implementado>.md` como referência de implantação das soluções em projetos futuros.
- FR29: [Usuário/Dev] encontra no `README` instruções quickstart reproduzíveis para executar o fluxo end‑to‑end.

### Observabilidade e Logs
- FR30: [Sistema] registra `ingest_logs` com (ticker, started_at, finished_at, rows_fetched, status, error_message).
- FR31: [Administrador] pode consultar logs para diagnosticar falhas de ingest.

### Segurança e Acesso (escopo mínimo local)
- FR32: [Sistema/DevOps] aplica permissões de arquivo para `dados/data.db` (owner-only) por padrão local.
- FR33: [Desenvolvedor] encontra orientações em docs para gerenciar credenciais via `.env` sem comitar segredos.

### Party Mode - Recomendações aplicadas (novos FRs)
- FR34: [Sistema] mantém `schema_version` e aplica migrações controladas ao DB (migrations traceáveis).
- FR35: [Sistema] suporta provedores via interface pluggable (adicionar/remover providers sem alterar core logic).
- FR36: [Sistema] executa retries com backoff configurável ao recuperar dados de provedores e registra tentativas em `ingest_logs`.
 - FR37: [CI] valida que qualquer CSV gerado inclua checksum SHA256; job CI verifica o checksum e falha em caso de mismatch (critério: mismatch -> pipeline fail).
- FR38: [Docs] `docs/phase-1-report.md` contém comando quickstart completo, checklist de aceitação e amostra de CSV com cabeçalho e metadados.

### FRs Adicionais (Party Mode refinements)
- FR39: [Administrador] pode consultar métricas de ingestão e telemetria (jobs por ticker, latência, taxas de erro) via comando ou relatório.
- FR40: [Sistema/Operador] realiza backups agendados do arquivo `dados/data.db` e permite restauração testada.
- FR41: [Desenvolvedor/Operador] aplica migrações de esquema versionadas que suportam rollback seguro.
- FR42: [Sistema] garante execução concorrente segura por ticker (um job por ticker por vez) para evitar corrupção em SQLite.
- FR43: [Process/Owner: Tech Writer/PM] garantir que requisitos ambíguos sejam reformulados no formato "[Actor] pode [capability]" e mapeados a critérios curtos de aceitação; aceitar como atividade de documentação.

### Acceptance Curta (FRs críticos)
- FR10 (Upsert): execução de ingest com mesmo (ticker,date) não cria duplicatas — verificado por teste unitário que insere 2x e confirma contagem inalterada.
- FR13 (Snapshot): `pipeline.ingest` gera snapshot CSV em `snapshots/` com checksum SHA256; rotina de verificação lê o CSV e valida o checksum.
- FR16 (Quickstart): `poetry run main --ticker <sample> --force-refresh` completa sem erro e gera snapshot CSV em `snapshots/`.
- FR40 (Backups): `backup --run` gera arquivo `backups/data-YYYYMMDD.db` e `restore --last` recupera DB em ambiente de teste (passa teste de integridade).
- FR41 (Migrations): `migrations status` mostra versão e `migrations apply`/`migrations rollback` funcionam em ambiente de teste.

## Scoping

### Escopo por Fase (consolidado)

- Fase 1 — Conexão com provedores de dados
  - Conectar Yahoo Finance + AlphaVantage (provedor secundário recomendado pelo Party Mode).
  - Persistir dados brutos em CSV: `raw/<provider>/<ticker>-YYYYMMDD.csv`.
  - Incluir metadados no CSV e/ou arquivo companion: `source`, `fetched_at`, `rows`, `checksum` (SHA256).
  - Validação de estrutura (schema check) e rejeição/flagging de dados inválidos.
  - CLI para testes de conexão e health‑check: `poetry run main --test-conn --provider <name> --health`.
  - Infra mínima: CI (instalar deps, rodar testes) e packaging com `poetry`.
  - Deliverable: `docs/phase-1-report.md` com checklist de aceitação e comandos reproduzíveis.

- Fase 2 — Banco de dados
  - Implementar SQLite local `dados/data.db` com esquema inicial (`prices`, `returns`, `ingest_logs`, `snapshots`, `metadata`).
  - Regras de validação ao inserir (types, PK `(ticker,date)`, constraints, upsert behavior).
  - Notebooks de validação/visualização em `notebooks/` mostrando ingest→DB→visual.
  - Transformação inicial: ajuste de preços e tratamento simples de gaps.
  - Deliverable: testes que comprovem persistência correta e notebooks reproduzíveis.

- Fase 3 — Infra para visualização
  - Criar `Dockerfile` e compose/runner para execução local.
  - Streamlit POC sob demanda que lê do SQLite e exibe gráficos básicos por ticker.
  - Deliverable: container que inicia Streamlit e demonstra visualização de um ticker.

- Fase 4 — Modelagem de carteiras e expansão de relatórios
  - Implementar módulo de modelagem (Markowitz POC), exportável como CSV/JSON.
  - Expandir notebooks e criar exemplos de `portfolio.generate` e scripts de batch.
  - Deliverable: relatório de POC com métricas (retorno esperado, volatilidade, Sharpe).

### Itens transversais e recomendações do Party Mode

- Provedor secundário: `AlphaVantage` (preferência recomendada pelo `architect` pela maturidade da API).
- Health‑check CLI: script automático que valida credenciais, quota, latência e gera relatório; deve suportar rollback/fallback quando falha.
- CSV schema mínimo: cabeçalho padrão + colunas de metadados (`source`,`fetched_at`,`rows`,`checksum`) e amostra de CSV incluída em `docs/`.
- CI: `poetry install`, `pytest` (unit + integration com mocks), verificação de geração de CSV + checksum; (opcional) `markdown-link-check` e `ruff`/`black` checks.
- Spike e estimativas: sugerido spike de 5–7 dias para prova de conceito de Fase 1 (2 provedores + CLI), Fase 1 completa em 1–2 semanas dependendo alocação.
- Documentação exigida: `docs/phase-1-report.md` com checklist, comandos reproduzíveis e amostra de CSV; repetido para cada fase (`docs/phase-2-report.md`, ...).

### Riscos e Mitigações (resumo)

- Provedor indisponível: mitigação por adaptador + cache + fallback raw CSV + health‑check automatizado.
- Dados inconsistentes: validar schema, rejeitar ou flag rows, inserir em `ingest_logs` com motivo e métricas; testes automatizados.
- Dívida de infra: iniciar CI + packaging já na Fase 1 para reduzir dívida técnica; usar spike curto para validar abordagens.

### Aceitação (por fase — resumo)

- Fase 1: duas integrações válidas + CSVs com checksum gerados via CLI; `docs/phase-1-report.md` anexado.
- Fase 2: ingest persistido no SQLite e notebooks reproduzíveis; testes que validam upsert e integridade; `docs/phase-2-report.md` anexado.
- Fase 3: Streamlit startável em container e exibindo dados de um ticker `docs/phase-3-report.md` anexado.
- Fase 4: portfólio POC gerado e relatórios exportáveis; `docs/phase-4-report.md` anexado.

### Estimativa de alto nível

- Fase 1 (MVP de integração): Spike 5–7 dias + entrega 1–2 semanas (1 dev full-time).
- Fase 2: 1–2 semanas adicionais para DB, validação e notebooks.
- Fase 3: 1 semana para Docker + Streamlit POC.
- Fase 4: 1–3 semanas dependendo profundidade da modelagem.

---

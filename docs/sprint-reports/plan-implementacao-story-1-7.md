# Plano de implementação — Sugestões pós-avaliação Story 1.7

Resumo do problema
------------------
A implementação da Story 1.7 já entrega compute_returns(), persistência idempotente e testes unitários. Foram identificadas sugestões de melhoria: (1) garantir compatibilidade e testes CI para diferentes versões de SQLite; (2) confirmar e endurecer o fallback de upsert preservando metadados (created_at); (3) adicionar testes de integração/E2E e property-based; (4) enriquecer documentação e exemplos de consumo (notebooks, queries); (5) adicionar smoke tests agendados/monitoramento e telemetria mais robusta.

Objetivo
--------
Entregar um conjunto de mudanças e validações que reduzam o risco operacional, garantam preservação de metadados em todos os runtimes suportados, melhorem a cobertura de testes (incluindo cenários de compatibilidade) e facilitem a adoção pelos consumidores de dados.

Escopo deste plano
-------------------
- Implementar mudanças e testes para: compatibilidade SQLite, fallback upsert, testes E2E/property-based, CI smoke/schedule e documentação de consumidor.
- Não inclui: migração de infra para Postgres (pode ser follow-up), mudanças em pipelines de produção fora do repositório.

Tarefas (ordem recomendada)
---------------------------
1) CI: matriz de compatibilidade SQLite
   - O que: adicionar workflow/step que execute a suíte relevante (tests/test_returns.py + testes de integração leves) em múltiplos ambientes SQLite (ex.: builds com imagens Docker contendo sqlite 3.22.x, 3.24.x, latest). Alternativa: mockar sqlite3.sqlite_version em testes unitários para simular runtimes.
   - Arquivos alvo: .github/workflows/ci.yml (ou novo workflow .github/workflows/sqlite-compat.yml), tests/
   - Dono: QA/Dev
   - Critério de aceite: pipeline CI executa a matriz e passa; reporta regressões específicas por versão.

2) Upsert fallback hardening
   - O que: revisar e consolidar a estratégia de fallback para `write_returns` e `write_prices` (atual: transactional UPDATE→INSERT fallback). Garantir documentação e cobertura de teste que valide que `created_at` é preservado no fallback.
   - Arquivos alvo: src/db.py, src/retorno.py
   - Dono: Dev
   - Critérios: adicionar unit test que força comportamento de fallback (por exemplo, monkeypatch em sqlite3.sqlite_version ou fixture que simule ambiente sem UPSERT) e verifica que created_at não é perdido; testes passam.

3) Testes de integração / E2E e property-based
   - O que: adicionar testes E2E que executem compute_returns contra um snapshot DB (ex.: tests/fixtures/sample_data.db) e property-based tests (Hypothesis) para invariantes do pct_change (e.g., monotonicidade de índices, consistência numérica). Incluir casos de feriados/gaps e séries com splits (validação via adj_close fallback).
   - Arquivos alvo: tests/e2e/test_returns_e2e.py, tests/property/test_returns_props.py
   - Dono: QA/Dev
   - Critério: testes E2E rodando no CI (pode ser em job separado) e property-based com seeds para reprodutibilidade.

4) Smoke tests agendados e workflow de orquestração
   - O que: criar workflow GitHub Actions agendado (daily) ou workflow de smoke que executa `compute-returns --dry-run` para um conjunto canário de tickers e armazena artifact/log/summary; falhas disparam alertas (PR/issue ou notificações de CI).
   - Arquivos alvo: .github/workflows/compute-returns-smoke.yml
   - Dono: Ops/Dev
   - Critério: workflow agendado dispara sem inserir dados de produção (dry-run) e publica artifacts de logs.

5) Documentação e exemplos de consumo
   - O que: adicionar um notebook de exemplo (docs/examples/retornos-usage.ipynb ou Markdown) mostrando: CLI dry-run, consulta SQL de exemplos, como usar returns em notebook (pandas), e update no docs/implementation-artifacts/retornos-conventions.md com exemplos e warning sobre versões SQLite.
   - Arquivos alvo: docs/examples/retornos-usage.md(.ipynb), docs/implementation-artifacts/retornos-conventions.md, docs/CHANGELOG.md
   - Dono: Tech Writer / Dev
   - Critério: exemplos funcionais e linkados do README/docs index; checklist de documentação completa.

6) Telemetria e monitoramento
   - O que: garantir que job telemetry (job_id, rows_written, duration_ms) seja coletada e, opcionalmente, exportável para Prometheus/Influx. Documentar env var para habilitar metrics server (já parcial: PROMETHEUS_METRICS env var). Adicionar teste para gravação de snapshot metadata.
   - Arquivos alvo: src/retorno.py (já em parte), docs/metrics.md
   - Dono: Dev / Ops
   - Critério: metadata registrada em snapshots e instruções para habilitar métricas.

7) Release checklist / Merge gating
   - O que: adicionar checklist no PR template ou template de merge: (a) testes unit+E2E passam na matriz, (b) docs atualizados, (c) smoke job criado/atualizado, (d) changelog entry e (e) qualquer requisito de versão do SQLite documentado.
   - Arquivos alvo: .github/PULL_REQUEST_TEMPLATE.md (ou docs/release-checklist.md)
   - Dono: PM/Dev
   - Critério: PR não pode ser mergeado sem checklist preenchido.

Dependências e observações técnicas
----------------------------------
- O repositório já implementa um fallback transacional para `write_returns` quando UPSERT não existe; o plano exige testes específicos que provoquem esse caminho e validação da preservação de `created_at`.
- O CI-matrix técnico pode ser implementado via Docker (imagens contendo versões específicas do sqlite) ou via mocks; Docker é mais realista para detectar diferenças de runtime.
- Para ambientes com múltiplos escritores concorrentes, considerar migrar para um RDBMS com suporte robusto a concorrência (Postgres) como follow-up.

Riscos e mitigação
------------------
- Risco: `INSERT OR REPLACE` destrói metadados → Mitigação: harden fallback (UPDATE→INSERT) já presente e cobertura de testes; requer validar em runtime com versões antigas do SQLite.
- Risco: CI matrix complexidade/tempo → Mitigação: separar jobs (fast unit tests vs compatibility job) e rodar a matriz apenas em branches principais/PRs ascendentes.
- Risco: performance ao persistir muitos tickers → Mitigação: medir tempo (smoke/perf) e considerar batch/transaction tuning + PRAGMA (WAL) já aplicado no src/db._apply_pragmas.

Resultados esperados / entregáveis
---------------------------------
- Workflow CI com matriz de compatibilidade e testes adicionais.
- Teste unitário que valida fallback e preservação de created_at.
- Testes E2E e property-based adicionados e integrados ao CI (job separado se necessário).
- Notebook de exemplo e documentação ampliada sobre uso/consumo.
- Workflow agendado (dry-run) como smoke test e instruções para habilitar métricas.
- PR/merge checklist atualizado.

Próximos passos imediatos
------------------------
1. Revisar plano e indicar prioridades (alta prioridade: 1 CI matrix + 2 fallback hardening + 3 testes E2E).  
2. Confirmar se deseja que eu (Copilot) crie issues no repositório para cada tarefa (opções: criar todas; criar apenas alta prioridade; não criar).  
3. Após confirmação, posso gerar rascunhos de issues/PRs e mudanças de arquivo (sempre pedindo autorização antes de commitar).

Notas finais
-----------
- O plano usa a base de código atual: src/retorno.py e src/db.py já contêm implementações e fallback transacional — portanto as mudanças tendem a ser testes, CI e documentação + pequenas correções de robustez.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>

---
title: Epic-1 - Relatório QA (Quinn)
agent: Quinn (qa)
role: QA Engineer
date: 2026-02-21
---

Objetivo QA:
- Avaliar cobertura de testes, pontos fracos em integração e riscos de flakiness.

Arquivos revisados (testes):
- tests/test_adapters.py, tests/test_retry.py, tests/test_mapper.py, tests/test_save_raw.py, tests/integration/*

Forças:
- Boas suites unitárias para adaptadores e mapper com mocks; tests simulam retries e cenários de sucesso/falha.
- Testes de checksum determinístico e validação pandera para o mapper.

Riscos e lacunas:
- Falta testes de persistência SQLite (story 1-6) e testes de concorrência/locking (1-9).
- Integração E2E mockada existe parcialmente, mas CI pipeline deve rodar smoke tests que garantam geração de CSV+checksum.

Ações recomendadas:
- Adicionar testes E2E mockados que executem pipeline.ingest --dry-run e validate snapshots in CI.
- Criar testes de concorrência para SQLite (multiprocess with same ticker) e documentar comportamento esperado.
- Definir thresholds de flaky (failing -> mark as flaky) e incluir job de nightly smoke/validation.

Prioridade: P0 para adicionar smoke E2E em CI; P1 para tests de concorrência.

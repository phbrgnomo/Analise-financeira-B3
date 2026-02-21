---
title: Epic-1 - Relatório UX (Sally)
agent: Sally (ux-designer)
role: UX Designer
date: 2026-02-21
---

Foco UX:
- Avaliar experiência do usuário quickstart CLI e playbooks / notebooks.

Observações rápidas:
- CLI fornece funcionalidade, mas mensagens informativas poderiam ser mais amigáveis (ex.: progresso do ingest, resumo pós-run com paths e checksums).
- Flags úteis (`--force-refresh`, `--dry-run`) existem; expor `--metrics` e `--job-id` para fácil diagnóstico seria valioso.
- Notebooks e Streamlit POC (quando disponível) devem incluir parâmetros de entrada visíveis e instruções passo-a-passo.

Recomendações:
- Melhorar saída de CLI: imprimir resumo com `job_id`, `filepath`, `raw_checksum`, rows_fetched e passos seguintes sugeridos.
- Atualizar playbook com screenshots de notebooks/streamlit e exemplos de outputs CSV.

Priority: P1 para CLI user messages; P2 para POC Streamlit UX polish.

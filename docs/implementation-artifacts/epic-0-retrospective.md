---
title: "Retrospectiva — Épico 0"
epic: 0
generated: 2026-02-18T00:00:00Z
author: Bob (Scrum Master)
---

# Retrospectiva — Épico 0

Resumo executivo
- Épico: 0
- Estado: Parcial (1 história em backlog)
- Total de histórias: 8
- Concluídas: 7
- Pendentes: 1 (`0-2-criar-readme-md-quickstart`)

Contexto
- Objetivo do épico: preparar infraestrutura do projeto (pyproject, CI, pre-commit, fixtures, quickstart e playbooks) para permitir contribuições reproduzíveis.
- Observação: Esta é a primeira retrospectiva registrada (não há retro anterior para comparar).

Principais achados
- Infraestrutura e qualidade: `pyproject.toml`, hooks de `pre-commit` (black/ruff), CI e fixtures foram implementados com sucesso — isso estabeleceu uma base estável para desenvolvimento.
- Quickstart incompleto: a história `0-2-criar-readme-md-quickstart` está em `backlog` e precisa ser finalizada para permitir um onboarding reprodutível de novos contribuidores.
- Lint/format: houve ocorrências detectadas por `ruff` (linhas longas) após aplicar hooks — recomenda-se executar `ruff --fix` e revisar manualmente onde necessário.
- Verificações de snapshot/checksum e integração: passos para snapshot e validação foram implementados (história `0-7`), útil para reprodutibilidade e integridade de dados.

Lições aprendidas
- Automatizar já nas primeiras histórias (pre-commit/CI) reduz atrito em PRs e contribuições — boa prática confirmada.
- Documentação de Quickstart é crítica para validação de fluxo end-to-end; deixar o quickstart incompleto atrasa experimentação por novos colaboradores.
- Ferramentas de lint/config (ruff/black) detectam problemas reais; incluir passo de correção automática no fluxo de PR evita falhas repetidas.

Riscos e bloqueios
- Sem o README quickstart finalizado, novos contribuintes poderão ter dificuldade em executar o fluxo end-to-end localmente.

Ações recomendadas (próximos passos)
1. Finalizar `0-2-criar-readme-md-quickstart` com exemplos end-to-end e `.env.example` — Responsável: Phbr — Prioridade: alta
2. Executar e commitar correções de lint automáticas: `poetry run ruff check --fix .` seguido de revisão manual das linhas remanescentes — Responsável: Dev (Amelia) — Prioridade: média
3. Adicionar um exemplo mínimo de quickstart no CI (smoke test) que execute `poetry run main --help` e um comando de exemplo com provider mocked — Responsável: QA (Quinn) / Dev — Prioridade: média
4. Validar e documentar localmente a geração de snapshots e checagem de checksums; atualizar instruções no README após completar 0-2 — Responsável: Phbr — Prioridade: média
5. Agendar follow-up: rodar retrospectiva final quando `0-2` estiver `completed` (revisar se novas lições aparecem) — Responsável: Bob (Scrum Master)

Preparação para o próximo épico (Épico 1)
- Dependências principais: adapters mínimos (yfinance), esquema canônico e pipeline de ingestão. A base técnica já foi estabelecida (config, lint, CI), porém o quickstart/documentação pendente pode dificultar testes manuais e demonstrações.
- Recomenda-se: completar `0-2` antes de abrir demasiadas tasks dependentes de demonstração/quickstart; entretanto, as histórias técnicas do Épico 1 podem progredir em paralelo se a equipe validar localmente os adaptadores.

Conclusão
- O time estabeleceu uma base sólida de tooling e qualidade. Finalizar a documentação de quickstart e aplicar as correções de lint aumentará a capacidade de onboarding e reduzirá retrabalho.

Gerado por: Bob (Scrum Master)

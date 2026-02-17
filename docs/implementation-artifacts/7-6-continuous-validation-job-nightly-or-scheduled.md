---
title: "7-6 Continuous validation job (nightly or scheduled)"
story: 7-6-continuous-validation-job-nightly-or-scheduled
status: ready-for-dev
---

# Story 7.6: continuous-validation-job-nightly-or-scheduled

Status: ready-for-dev

## Story

As a Engenheiro de DevOps / Operador de plataforma,
I want um job de validação contínua que rode nightly ou em agendamento configurável,
so that possamos verificar automaticamente a integridade dos artefatos de migração, snapshots e checksums antes/apos mudanças e detectar regressões rapidamente.

## Acceptance Criteria

1. O job pode ser agendado para rodar nightly (cron) ou em intervalos configuráveis via variáveis/CRON.
2. O job executa um conjunto definido de validações: checksums de snapshots, restauração parcial de snapshot (smoke), e checagens de integridade de dados.
3. Falhas do job geram artefatos de diagnóstico (logs, saída de comparação de checksums) e enviam alerta/issue para o canal configurado.
4. O job roda em ambiente de CI (ex.: GitHub Actions) e também pode ser executado localmente via CLI com flags de modo e targets.
5. Documentação clara do runbook e passos para investigação e rollback estão incluídos em `docs/implementation-artifacts`.
6. Métricas básicas (último run, sucesso/fracasso, duração) são registradas e expostas em formato legível (log ou arquivo JSON) para consumo por sistemas de monitoramento.

## Tasks / Subtasks

- [ ] Implementar pipeline/CI job (GitHub Actions / GitLab CI) com suporte a CRON e trigger manual
  - [ ] Script de execução: `scripts/validate_continuous.py` ou `make validate-continuous`
  - [ ] Implementar etapas: preparar ambiente, baixar snapshots, calcular checksums, tentar restore-smoke, comparar resultados
- [ ] Gerar artefatos de diagnóstico e persistir em `logs/validation/YYYY-MM-DD` e em saída JSON
- [ ] Adicionar integração com canal de alerta (ex.: criação automática de issue, webhook ou notificação)
- [ ] Documentar runbook e instruções de investigação e rollback em `docs/implementation-artifacts/7-6-continuous-validation-job-nightly-or-scheduled.md`
- [ ] Adicionar testes básicos de integração que rodem no job (smoke tests)

## Dev Notes

- Preferir soluções simples e reproduzíveis: scripts Python + utilitários do repositório.
- Job deve ser idempotente e seguro para executar contra snapshots de staging/test.
- Evitar operações destrutivas em ambientes de produção; restore-smoke deve usar ambientes/paths controlados.
- Parametrizar via variáveis de ambiente e arquivo de configuração (ex.: `VALIDATION_TARGETS`, `CRON_SCHEDULE`, `ALERT_WEBHOOK`).

### Project Structure Notes

- Local sugerido para implementação: `scripts/` para runners, `ci/` ou `.github/workflows/` para pipelines, e `docs/implementation-artifacts/` para runbook.
- Arquivos de saída e logs: `logs/validation/` sob o repositório (ou artefatos CI).

### References

- Fonte: [sprint-status.yaml](docs/implementation-artifacts/sprint-status.yaml) (entrada `7-6-continuous-validation-job-nightly-or-scheduled`)
- Arquitetura: revisar `docs/planning-artifacts/architecture.md` se existir para requisitos de infra e segurança

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Debug Log References

- Workflow: _bmad/bmm/workflows/4-implementation/create-story/workflow.yaml
- Template: _bmad/bmm/workflows/4-implementation/create-story/template.md

### Completion Notes List

- Ultimate context engine analysis (automated YOLO run) completada de forma mínima para gerar o arquivo de história.

### File List

- docs/implementation-artifacts/7-6-continuous-validation-job-nightly-or-scheduled.md

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/

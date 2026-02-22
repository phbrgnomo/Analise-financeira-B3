---
title: "4-6 Health checks and readiness probes for local deployments"
story: 4-6-health-checks-and-readiness-probes-for-local-deployments
status: ready-for-dev
---

# Health checks and readiness probes for local deployments

Resumo: adicionar endpoints e comandos para health/readiness em deploys locais, úteis para integração com orquestradores e CI.

## Critérios de Aceitação
- Endpoint /health responde status
- Readiness verifica dependências críticas
- Documentação de uso local e em CI

## Tarefas
- Implementar endpoints simples
- Adicionar checks configuráveis
- Testes e documentação

## Notas
- Focar em verificações leves e rápidas.
﻿# Story 4.6: Health checks and readiness probes for local deployments

Status: ready-for-dev

## Story

Como desenvolvedor/operador,
quero endpoints e probes de health e readiness para as execuções locais,
para que os deployments locais sejam verificáveis, integráveis com orquestradores e fáceis de depurar.

## Acceptance Criteria

1. Existe um endpoint de *liveness* que responde 200 quando a aplicação está viva.
2. Existe um endpoint de *readiness* que verifica dependências críticas (ex.: arquivos de configuração, conexão mínima com DB/mocks) e responde 200 somente quando pronto.
3. Probes podem ser usadas por orquestradores locais (docker-compose, k8s local, devcontainers).
4. Implementação não bloqueia inicialização longa de dependências; readiness pode falhar inicialmente e recuperar.
5. Documentação curta com como testar localmente e exemplos de `curl`/`kubectl`/`docker-compose`.
6. Testes unitários/integrados cobrindo comportamento dos endpoints (simulação de dependências OK/falha).

## Tasks / Subtasks

- [ ] Adicionar endpoints `GET /health` (liveness) e `GET /ready` (readiness)
  - [ ] Implementar verificações internas mínimas (config, versão, cache/local state)
  - [ ] Implementar verificação de dependências com timeouts configuráveis
- [ ] Expor configuração via variáveis de ambiente e documentar defaults
- [ ] Adicionar exemplos de `docker-compose` e `k8s` readiness/liveness snippets na documentação
- [ ] Escrever testes que cubram success e failure cases para `ready`
- [ ] Atualizar `README`/docs com instruções de teste local

## Dev Notes

- Linguagem e estrutura: Projeto em Python com pacote principal `src/` e entrypoint `src.main`.
- Preferir implementação leve sem adicionar dependências pesadas — use standard library ou dependências já presentes (pandas/numpy não aplicam aqui). Se for necessário, justificar versão e adicionar ao `pyproject.toml`.
- Timeouts e retries: configurar via variáveis ambiente `HEALTH_READY_TIMEOUT` e `HEALTH_READY_RETRIES`.
- Expor métricas básicas (uptime, versão) no endpoint de liveness quando possível.

### Project Structure Notes

- Paths sugeridos:
  - Handlers/routers: `src/` (seguir padrões existentes em `src.main`)
  - Testes: `tests/` (seguir fixtures já existentes em `tests/`)
- Não alterar estruturas existentes; adicionar módulos pequenos e isolados para facilitar testes.

### References

- Source: [src/main.py](src/main.py)
- Project conventions: [docs/implementation-artifacts](docs/implementation-artifacts)

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Debug Log References

- (registro gerado pelo agente durante criação da story)

### Completion Notes List

- Ultimate context engine analysis completed for story 4.6

### File List

- docs/implementation-artifacts/4-6-health-checks-and-readiness-probes-for-local-deployments.md

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/140

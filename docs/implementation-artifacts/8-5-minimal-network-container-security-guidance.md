---
title: "8-5 Minimal network & container security guidance"
story: 8-5-minimal-network-container-security-guidance
status: ready-for-dev
---

# História 8.5: Diretrizes mínimas de segurança de rede e containers

Status: ready-for-dev

## História

Como engenheiro(a) de DevOps,
quero um conjunto mínimo de diretrizes e tarefas para garantir a segurança de rede e de containers,
para que as imagens e os ambientes de execução estejam protegidos contra vetores comuns de ataque e riscos operacionais.

## Critérios de Aceitação

1. Políticas de rede (NetworkPolicy) documentadas com exemplos que implementem deny-by-default e regras mínimas por serviço.
2. Processo automatizado de scanner de imagens integrado ao CI (ex.: Trivy) que bloqueie deploys com vulnerabilidades de alta severidade.
3. Manifests de exemplo contendo `securityContext` com `runAsNonRoot`, `allowPrivilegeEscalation: false`, `readonlyRootFilesystem` e `dropCapabilities`.
4. Requests/limits e probes definidos nos manifests de exemplo para evitar esgotamento de recursos.
5. Checklist de revisão para PRs de infraestrutura e containers e checagens automatizadas no pipeline.
6. Guia de hardening básico para hosts de container (atualizações, firewall, usuários mínimos).

## Tarefas / Subtarefas

- [ ] Criar documento com políticas de rede e exemplos (Calico/NetworkPolicy)
  - [ ] Exemplos: deny-by-default, permitir apenas tráfego necessário por namespace/service
- [ ] Integrar scanner de imagens no pipeline CI (ex.: Trivy)
  - [ ] Adicionar passo de CI que falha em vulnerabilidades de severidade alta/critica
- [ ] Fornecer manifests de Deployment/Pod com `securityContext` e configurações recomendadas
  - [ ] Validar `readonlyRootFilesystem`, `dropCapabilities` e `runAsNonRoot`
- [ ] Definir requests/limits e readiness/liveness probes nos exemplos
- [ ] Criar checklist de revisão de PRs para infra/containers
- [ ] (Opcional) Exemplo de configuração mínima de runtime (containerd/docker) e hardening do host

## Notas para Desenvolvedores

- Preferir imagens oficiais e enxutas com tags versionadas (ex.: distroless, alpine), evitar `latest`.
- Não executar containers como root; usar `runAsNonRoot=true` e dropar capacidades desnecessárias.
- Evitar `privileged` e `hostNetwork` sempre que possível; justificar e documentar quando usados.
- Incluir scanner de imagem e políticas de admissão (OPA/Gatekeeper) quando aplicável.
- Fornecer manifests prontos para testes locais e para ambiente de CI/CD.

### Notas sobre Estrutura do Projeto

- Sugestão de localização para docs e exemplos: docs/implementation-artifacts/security/
- Nomes sugeridos para manifests de exemplo: `epic-8-5-*-example.yaml` ou `k8s/<servico>/<nome>.yaml`
- Alterações em configurações centrais devem ocorrer via PR com revisão de segurança.

### Referências

- Source: melhores práticas de segurança de containers e Kubernetes (documentação externa recomendada)
- Ferramentas recomendadas: Trivy (scanner de imagens), Calico/NetworkPolicy, OPA/Gatekeeper

## Registro do Agente Dev

### Modelo do Agente Utilizado

GPT-5 mini (modo YOLO - execução automatizada)

### Notas de Conclusão

- Análise de contexto executada em modo YOLO; arquivo criado com critérios, tarefas e guardrails para implementação.
- Status definido como `ready-for-dev`.

### Lista de Arquivos

- docs/implementation-artifacts/8-5-minimal-network-container-security-guidance.md

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/165

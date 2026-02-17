 # Story 1.8: Implementar retries/backoff no adaptador crítico

 Status: ready-for-dev

 ## Story

 As a engenheiro de integração,
 I want implementar retries com backoff exponencial no adaptador crítico,
 so that chamadas falhascas temporárias sejam automaticamente retomadas e reduzam falhas em produção.

 ## Acceptance Criteria

 1. O adaptador aplica retry com backoff exponencial em chamadas externas críticas (HTTP/IO) por padrão.
 2. Configurações: `max_attempts`, `initial_delay_ms`, `max_delay_ms`, `backoff_factor`, `retry_on_status_codes` devem ser configuráveis via variável/arquivo de configuração.
 3. Retries são aplicados apenas a operações idempotentes ou que possuam mecanismos de deduplicação; operações não-idempotentes devem ser excluídas por configuração explícita.
 4. Logs estruturados em cada tentativa (tentativa número, delay aplicado, erro detectado) e métricas expostas (retry_count, success_after_retry, permanent_failures).
 5. Cobertura de testes: unit tests para lógica de backoff e integração mockada cobrindo sucesso no 1º try, sucesso após N retries, e falha permanente após exceder `max_attempts`.
 6. Timeouts e cancelamento respeitados: retry não deve bloquear indefinidamente e deve respeitar timeouts já existentes.
 7. Documentação breve no README do adaptador com exemplos de configuração e comportamento esperado.

 ## Tasks / Subtasks

 - [ ] Task 1: Implementar utilitário de retries/backoff
   - [ ] Subtask 1.1: Implementar função `retry_with_backoff` com parametros configuráveis
   - [ ] Subtask 1.2: Adicionar tratamento de exceções e lógica de retry-on-status
 - [ ] Task 2: Integrar utilitário no adaptador crítico
   - [ ] Subtask 2.1: Identificar pontos de chamada (client HTTP / IO) e aplicar wrapper
 - [ ] Task 3: Expor configuração via arquivo/env (ex.: `ADAPTER_RETRY_MAX_ATTEMPTS`)
 - [ ] Task 4: Adicionar logs e métricas (preferência por formato JSON/structured)
 - [ ] Task 5: Escrever testes unitários e de integração com mocks
 - [ ] Task 6: Atualizar documentação do adaptador e exemplos de uso

 ## Dev Notes

 - Requisitos críticos: garantir idempotência ou deduplicação; evitar retries em operações que alteram estado sem proteção.
 - Preferência por implementar utilitário genérico no módulo do adaptador (ex.: `src/dados_b3` ou `src/utils`) seguindo padrões existentes do repositório.
 - Evitar adicionar dependências pesadas. Se já existe utilitário similar no repo, estender/reusar-o.
 - Respeitar timeouts configurados e não aumentar implicitamente o timeout total sem expor configuração.

 ### Project Structure Notes

 - Manter implementações em módulos coerentes com `src/` (ex.: `src/adapters/critical_adapter.py` ou dentro de `src/dados_b3.py` se for o adaptador relevante).
 - Nomear funções públicas com prefixo `retry_` ou documentar na API do adaptador.

 ### References

 - Source: docs/implementation-artifacts (histórico de stories)
 - Source: _bmad/bmm/workflows/4-implementation/create-story/template.md

 ## Dev Agent Record

 ### Agent Model Used

 GPT-5 mini

 ### Debug Log References

 - Registrar logs de tentativa no formato: `{ "story":"1-8", "attempt":n, "error":"...", "delay_ms":... }`

 ### Completion Notes List

 - Ultimate context engine analysis (YOLO): gera guia consolidado para implementação.

 ### File List

 - docs/implementation-artifacts/1-8-implementar-retries-backoff-no-adaptador-critico.md


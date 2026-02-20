---
title: Checklist de PR - Adapters
---

# Checklist de PR — Adaptadores

Use este checklist ao abrir um PR que altera ou adiciona adaptadores (ou o `Adapter` base).

- **Descrição do PR**: explique a motivação, mudanças principais e impacto em compatibilidade.
- **Testes locais**: suite completa `poetry run pytest` rodou sem falhas.
- **Novos testes**: casos unitários e/ou de integração para cobrir comportamento novo/alterado.
- **Contract Tests**: se o `Adapter` base mudou, adicione/atualize testes de contrato para provedores existentes.
- **Mensagens de erro & exceções**: verifique que testes não dependem de strings exatas; preferir checar tipo/atributos.
- **Compatibilidade de testes**: preserve shims usados em testes (ex.: `src.adapters.yfinance_adapter.web.DataReader`) ou atualize testes para injeção/patch apropriado.
- **Documentação**: inclui link para `docs/modules/adapter-guidelines.md` e notas de migração se o comportamento mudou.
- **Changelog / Migration Notes**: descreva passos que consumidores/integrações precisam seguir (ex.: `_fetch_once` agora é abstrato).
- **Observability**: verifique logs/contexto (`log_context`) e metadados (`df.attrs`) são populados conforme o guia.
- **Performance / Rate Limits**: se aplicável, documente como tratar rate limits e se há backoff global configurável.
- **CI**: pipeline do GitHub Actions passa (`.github/workflows/ci.yml`).
- **Security**: não incluir chaves/segredos; validar dependências novas.

Observação: PRs que alteram o `Adapter` base podem afetar múltiplos adaptadores — prefira pequenos PRs com migração clara ou fornecer um PR de acompanhamento que atualize todos os adaptadores afetados.

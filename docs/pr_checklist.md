**PR Checklist**

- **Descrição:** o PR tem uma descrição clara do problema e da solução?
- **Ticket / Story:** referência ao issue/story/PR relacionado (ex: #188)
- **Testes:** novos comportamentos têm testes automatizados e todos os testes passam (`poetry run pytest`).
- **Lint/Format:** `pre-commit` e `ruff`/`black` aplicados; não há erros de lint.
- **Migrações:** se houve mudança de schema, inclua arquivo de migração em `migrations/` e steps de rollback.
- **Dados Sensíveis:** não incluir segredos, tokens ou `.env` no PR.
- **Documentação:** atualizar `docs/` quando necessário (ex.: instruções de uso, exemplos, changelog).
- **CI:** pipeline do GitHub Actions deve passar (lint, unit, integration).
- **Performance/Impact:** explique impactos de performance ou requisitos de infra/ops.
- **Segurança:** revisar input validation, SQL parameterization e permissões.
- **Rollback / Compatibilidade:** o PR é compatível com deploys blue/green e tem plano de rollback quando aplicável.
- **Checklist de reviewers:** indique que tipos de revisão são necessários (arquitetura, segurança, banco, testes).

Comandos úteis para revisão local:

```bash
# instalar dependências
poetry install

# rodar lint
poetry run ruff check src tests || true
poetry run black --check . || true

# rodar testes
poetry run pytest -q
```

Quando tudo estiver ok, adicione os reviewers e marque o PR como pronto para revisão.

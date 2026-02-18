# Sprint Report — Story 0.4: CI skeleton implementation

Status: in-progress (sprint-status updated)

Resumo

Implementação do pipeline de CI inicial conforme Story 0.4: adição de workflow GitHub Actions (`.github/workflows/ci.yml`) com jobs `lint`, `test` e `smoke`; cache para Poetry; upload de artifacts em caso de falha; testes auxiliares em `tests/ci` para execução determinística em CI.

Arquivos alterados/criados

- .github/workflows/ci.yml — workflow CI (modificado)
- tests/ci/smoke.sh — script de smoke
- tests/ci/README.md — orientações de helpers CI
- tests/ci/conftest.py — fixture `snapshot_dir`
- tests/ci/test_mock_provider.py — teste de provider mocked e snapshot
- README.md — seção rápida de CI e badge
- docs/implementation-artifacts/sprint-status.yaml — status atualizado para in-progress
- docs/implementation-artifacts/0-4-criar-skeleton-de-ci-github-workflows-ci-yml.md — subtasks atualizadas e Dev Agent Record

Comandos reproduzíveis

# Instalar dependências (recomendado: usar Poetry)
poetry install

# Executar suíte de testes completa
poetry run pytest -q

# Executar apenas testes CI helpers
poetry run pytest tests/ci -q

O job `test` no CI grava `reports/junit.xml` que é enviado como artifact em caso de falha.

Snapshots e verificações

- Testes CI geram snapshots em `snapshots_test/` durante execução local (a mesma pasta será coletada como artifact no CI se configurado).
- Cada snapshot inclui um arquivo `.checksum` com SHA256.

Segurança e segredos

- `.env` está listado em `.gitignore` e não deve ser comitado.
- `.env.example` existe na raiz com instruções; não contém segredos.
- No CI, recomenda-se usar GitHub Secrets (`Settings → Secrets`) para chaves e tokens.

Próximos passos

1. Validar workflow no GitHub Actions através de um PR (recomendado).
2. Expandir fixtures em `tests/ci` para cobrir outros adapters/provedores.
3. Adicionar badges de jobs individuais se desejar (atualmente há badge para workflow `CI`).

Notas do Dev Agent

Implementação corresponde aos itens listados na story; testes locais e CI-helpers passaram localmente. Abrir PR para validação em runner GitHub para confirmação final.

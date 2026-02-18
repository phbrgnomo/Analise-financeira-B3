# Sprint Report — Story 0.4: CI skeleton implementation

Status: completed (verified locally)

Resumo

Implementação do pipeline de CI inicial conforme Story 0.4: adição de workflow GitHub Actions (`.github/workflows/ci.yml`) com jobs `lint`, `test` e `smoke`; cache para Poetry; upload de artifacts em caso de falha; testes auxiliares em `tests/ci` para execução determinística em CI. Remoção de snapshots versionados e uso de diretório temporário para artefatos de teste.

Validação

- Testes locais: `poetry run pytest` → todos os testes passaram.
- Testes CI helpers: `poetry run pytest tests/ci` → 1 passed.
- Verificado que `snapshot_dir` escreve em diretório temporário e que snapshots não estão versionados.

Arquivos alterados/criados

- .github/workflows/ci.yml — workflow CI (modificado)
- tests/ci/smoke.sh — script de smoke
- tests/ci/README.md — orientações de helpers CI
- tests/ci/conftest.py — fixture `snapshot_dir` (usa tmp path)
- tests/ci/test_mock_provider.py — teste de provider mocked e snapshot
- docs/implementation-artifacts/sprint-status.yaml — status atualizado para `completed`
- docs/implementation-artifacts/0-4-criar-skeleton-de-ci-github-workflows-ci-yml.md — subtasks atualizadas e Dev Agent Record

Comandos reproduzíveis

```bash
# Instalar dependências (recomendado: usar Poetry)
poetry install

# Executar suíte de testes completa
poetry run pytest -q

# Executar apenas testes CI helpers
poetry run pytest tests/ci -q
```

Snapshots e verificações

- Testes CI geram snapshots em diretório temporário via fixture `snapshot_dir` durante a execução (esse diretório pode ser coletado como artifact no CI se configurado).
- Cada snapshot inclui um arquivo `.checksum` com SHA256.

Segurança e segredos

- `.env` está listado em `.gitignore` e não deve ser comitado.
- `.env.example` existe na raiz com instruções; não contém segredos.
- No CI, recomenda-se usar GitHub Secrets (`Settings → Secrets`) para chaves e tokens.


Notas do Dev Agent

Implementação corresponde aos itens listados na story; testes locais e CI-helpers passaram. Aguarda validação em runner GitHub via PR.

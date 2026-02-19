---
story: 0-8-playbooks-quickstart-e-ux-minimal
date: 2026-02-18
author: Phbr / Amelia (Dev Agent)
status: review
---

# Relatório de implantação — Story 0.8

Resumo

Este documento registra a conclusão da Story 0.8 (Playbooks: Quickstart e UX) conforme o requisito FR28 do PRD. Foram criados playbooks operacionais e verificados os artefatos básicos em ambiente de desenvolvimento local.

Artefatos criados

- `docs/playbooks/quickstart-ticker.md` — passo a passo rápido para executar ingest→persist→snapshot→notebook
- `docs/playbooks/ux.md` — expectativas mínimas de UX para CLI, notebooks e Streamlit POC

Arquivos modificados/atualizados

- `README.md` — links para os playbooks na seção Quickstart
- `docs/implementation-artifacts/0-8-playbooks-quickstart-e-ux-minimal-docs-playbooks-quickstart-ticker-md-docs-playbooks-ux-md.md` — checklist e Dev Agent Record atualizados
- `docs/implementation-artifacts/sprint-status.yaml` — status da story atualizado para `review`

Validação local (passos executados)

1. Conferir playbooks (leitura rápida):

```bash
sed -n '1,120p' docs/playbooks/quickstart-ticker.md
sed -n '1,120p' docs/playbooks/ux.md
```

2. Executar quickstart (exemplo) — ambiente local; este repositório fornece CLI `main`:

```bash
poetry run main --ticker PETR4.SA --force-refresh
```

3. Verificar snapshot gerado (exemplo):

```bash
ls -l snapshots/PETR4_snapshot.csv
sha256sum snapshots/PETR4_snapshot.csv
```

4. Executar suíte de testes e verificar regressões:

```bash
poetry run pytest -q
# Resultado esperado: 10 passed, 0 failed (no ambiente local onde testes foram executados)
```

Observações e notas

- Os playbooks são documentos iniciais (mínimos) — contêm comandos reproduzíveis, checklist e exemplos de verificação (checksum). São suficientes para um colaborador reproduzir o fluxo em ambiente dev.
- Em CI, recomendo adicionar um job que execute um teste end‑to‑end mockado (pipeline.ingest com mocking de provider) e valide que o snapshot e checksum sejam gerados conforme FR13/FR37.
- Para registro formal por release, podemos criar `docs/sprint-reports/0-8-playbooks-implantacao.md` (este arquivo) e anexar fixtures/snapshots de exemplo em `snapshots_test/` como evidência.

Próximos passos recomendados

- Abrir PR com estas mudanças apontando para `dev-story-0-8` → `master` e pedir revisão (posso abrir o PR se desejar).
- Adicionar uma entrada no CI para validar quickstart em modo mock (evita chamadas reais a provedores) e validar checksum automaticamente.
- Opcional: criar `docs/sprint-reports/0-8-playbooks-implantacao-examples.md` contendo outputs de comandos (sha256, primeiras linhas do CSV) como evidência encurtada.

Contato / Issue

- Issue relacionada: https://github.com/phbrgnomo/Analise-financeira-B3/issues/111

---

Fim do relatório.

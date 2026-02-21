## Validação de Snapshots (checksums)

Objetivo
- Garantir que os arquivos de snapshot no repositório correspondem a um manifesto de checksums conhecido.

Como usar

1. Gerar/atualizar o manifesto (executar localmente quando os snapshots são atualizados):

```bash
python scripts/validate_snapshots.py --dir snapshots --manifest snapshots/checksums.json --update
```

2. Validar (CI faz isso automaticamente):

```bash
python scripts/validate_snapshots.py --dir snapshots --manifest snapshots/checksums.json
```

Design
- Hash usado: `sha256` por arquivo.
- Formato do manifesto: JSON, chave `files` com mapping `path -> {"sha256": "..."}`.
- Política: incluir apenas arquivos determinísticos que fazem parte do snapshot de referência.

CI
- Workflow: `.github/workflows/checks-snapshots.yml` roda em PRs e pushes.

Atualizar manifesto
- Use a flag `--update` para regenerar o manifesto após confirmação que os snapshots foram intencionalmente alterados.

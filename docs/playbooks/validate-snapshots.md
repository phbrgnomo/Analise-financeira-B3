## Validação de Snapshots (checksums)

Objetivo
- Garantir que os snapshots determinísticos gerados no fluxo local/CI
	correspondem ao manifesto canônico versionado em `snapshots/checksums.json`.

Como usar

1. Gerar snapshots determinísticos em diretório temporário:

```bash
mkdir -p ./snapshots_test
SNAPSHOT_DIR=$PWD/snapshots_test poetry run python scripts/generate_ci_snapshot.py
```

2. Validar contra o manifesto canônico:

```bash
python scripts/validate_snapshots.py --dir snapshots_test --manifest snapshots/checksums.json --allow-external
```

3. Gerar/atualizar o manifesto (somente quando o snapshot determinístico de referência mudar intencionalmente):

```bash
python scripts/validate_snapshots.py --dir snapshots_test --manifest snapshots/checksums.json --update --allow-external
```

Design
- Hash usado: `sha256` por arquivo.
- Formato do manifesto: JSON, chave `files` com mapping `path -> {"sha256": "..."}`.
- Política: versionar apenas o manifesto canônico; os CSVs de validação são
	gerados em diretórios temporários (`snapshots_test/`, `tmp_snapshots/`) e
	não devem ser commitados.

CI
- Workflow: `.github/workflows/checks-snapshots.yml` gera snapshots
	determinísticos em `tmp_snapshots/snapshots_test` e valida o resultado
	contra `snapshots/checksums.json`.

Atualizar manifesto
- Recrie primeiro `snapshots_test/` com `scripts/generate_ci_snapshot.py` e,
  em seguida, use `--update --allow-external` para regenerar
  `snapshots/checksums.json`.

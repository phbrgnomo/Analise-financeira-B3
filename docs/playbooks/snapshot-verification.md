# Snapshot verification — resumo rápido

- Comandos para validar e (re)gerar manifest de snapshots.

### Pré-requisitos
- Instalar dependências do projeto: `poetry install`

Validar snapshots usando o manifest existente:

```bash
python scripts/validate_snapshots.py --dir snapshots --manifest snapshots/checksums.json
```

Gerar/atualizar um manifest a partir de um diretório (ex.: para testes locais):

```bash
python scripts/validate_snapshots.py --dir <tmp_dir> --manifest <tmp_manifest.json> --update --allow-external
```

### Notas sobre determinismo
- Para testes e E2E, gere arquivos com timestamp controlado (ex.: `--ts` ou variável de ambiente) ou crie os CSVs de forma determinística. O código de verificação suporta `--allow-external` para remapear nomes-base dos arquivos externos para `snapshots/<basename>` durante validação.

### Códigos de saída relevantes
- `0` — todos os snapshots batem com o manifesto
- `2` — diferenças encontradas ou erro de validação de argumentos
- `3` — erro crítico (ex.: colisão de nomes-base ao remapear com `--allow-external`)

### Recomendação
- Em CI prefira validar contra o diretório `snapshots/` do repositório sem `--allow-external`.
- Use `tmp_path` e nomes/timestamps fixos para evitar flakiness em testes.

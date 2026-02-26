# Quickstart: Reproduzir Acceptance CI localmente

Passos mínimos para reproduzir o fluxo do workflow `acceptance.yml` localmente.

1. Instalar dependências (Poetry):

```bash
poetry install
```

2. Inicializar DB (opcional):

```bash
poetry run python scripts/init_ingest_db.py --db dados/data.db
```

3. Gerar snapshot determinístico em um diretório temporário:

```bash
mkdir -p ./snapshots_test
SNAPSHOT_DIR=$PWD/snapshots_test ./examples/run_quickstart_example.sh
# ou
SNAPSHOT_DIR=$PWD/snapshots_test poetry run python scripts/run_save_raw_example.py --out-dir snapshots_test
```

4. Validar checksums/manifest:

```bash
poetry run python scripts/validate_snapshots.py --dir snapshots_test --manifest snapshots/checksums.json --allow-external
# ou usar o wrapper
poetry run python scripts/verify_snapshot.py --dir snapshots_test --manifest snapshots/checksums.json --allow-external
```

5. Rodar teste E2E localmente (opcional):

```bash
NETWORK_MODE=playback poetry run pytest -q tests/e2e/test_acceptance_snapshot.py
```

Dicas:
- Use `NETWORK_MODE=playback` para evitar chamadas de rede e garantir determinismo no CI.
- Se precisar gravar fixtures reais, use `NETWORK_MODE=record` em ambiente controlado.

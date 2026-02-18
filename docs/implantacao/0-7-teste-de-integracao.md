# Implantação: Teste de integração quickstart (mocked) e passo CI para checksum

Passo-a-passo para rodar localmente e em CI:

1. Fixtures de teste estão em `tests/fixtures/`:
   - `sample_snapshot.csv` — CSV de amostra usado pelo teste
   - `expected_snapshot.checksum` — checksum SHA256 esperado do CSV
2. Teste de integração: `tests/integration/test_quickstart_mocked.py` — copia a fixture para `snapshots_test/`, valida cabeçalho e SHA256 e grava `.checksum` paralelo.
3. CI: Job `integration` em `.github/workflows/ci.yml` executa os testes de integração e publica `snapshots_test/**` como artefato para inspeção manual.
4. Para rodar localmente:

```bash
poetry install
poetry run pytest -q tests/integration -k quickstart_mocked
```

5. Regras de checksum: SHA256 sobre o conteúdo bruto do CSV (bytes UTF-8). Arquivo `.checksum` contém apenas o hash hex em ASCII.

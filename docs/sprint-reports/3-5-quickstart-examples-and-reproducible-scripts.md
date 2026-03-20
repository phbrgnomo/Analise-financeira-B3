---
story_key: 3-5-quickstart-examples-and-reproducible-scripts
status: completed
---

# Sprint Report: Quickstart examples and reproducible scripts (Story 3.5)

## O que foi implementado

- Criado o script **`examples/run_quickstart_example.sh`** como ponto de entrada para executar o pipeline em modo determinístico (sem rede) usando o fixture:
  - `tests/fixtures/sample_ticker.csv`
- O script agora respeita variáveis de ambiente:
  - `DATA_DIR`, `SNAPSHOT_DIR`, `OUTPUTS_DIR`, `LOG_DIR`
- Adicionado suporte ao argumento `--config <file>` (ex.: `.env`) para carregar configurações de ambiente.
- A saída em `--format json` produz uma única linha JSON (pronta para CI) contendo `job_id`, `status`, `elapsed_sec`, `snapshot` e `rows`.

## Testes

- Adicionado teste `tests/test_run_quickstart_example.py` que:
  - Executa `examples/run_quickstart_example.sh --no-network --format json` em diretório temporário
  - Verifica que o script sai com código 0
  - Verifica que um snapshot CSV e `.checksum` foram criados em `snapshots/`
  - Verifica que um log foi escrito em `logs/` contendo `job_id` e `status`

## Integração CI

- Workflow `ci.yml` atualizado para executar o script como smoke test durante o job `test`.
- Artifacts (`outputs/`, `logs/`, `snapshots/`) são enviados em caso de falha para facilitar debugging.

## Observações

- A saída em JSON é derivada do próprio CLI (`poetry run main`) e contém detalhes por ticker. O script extrai um resumo compacto para uso em pipelines.
- O script mantém o comportamento de não gravar nada no repositório por padrão, mas permite salvar saídas em `outputs/` quando desejado.

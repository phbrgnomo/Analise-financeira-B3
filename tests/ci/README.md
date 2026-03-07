CI helpers for repository

**Scripts para auxiliar na execução de testes e validações no workflow de CI.**

- `ci_orchestrator.sh`: script shell para orquestrar a execução dos scripts de CI e coletar resultados.
- `smoke.sh`: script de smoke test executado pelo job `smoke` no workflow CI.
- `integration.sh`: script de teste de integração executado pelo job `integration` no workflow CI. Após os testes, ele gera `PETR4_snapshot.csv` em `SNAPSHOT_DIR` e valida o resultado contra `snapshots/checksums.json`.
- `lint.sh`: script de lint executado pelo job `lint` no workflow CI.
- `validate_snapshots.sh`: valida os snapshots gerados para a CI (por padrão em `snapshots_test/` ou no diretório apontado por `SNAPSHOT_DIR`) comparando checksums com o manifesto canônico (`snapshots/checksums.json`). O script imprime diferenças encontradas (arquivos faltantes, checksums divergentes) e retorna código de saída não-zero em caso de falha. Executar localmente:

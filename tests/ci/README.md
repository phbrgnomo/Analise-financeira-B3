CI helpers for repository

**Scripts para auxiliar na execução de testes e validações no workflow de CI.**

- `ci_orchestrator.sh`: script shell para orquestrar a execução dos scripts de CI e coletar resultados.
- `smoke.sh`: script de smoke test executado pelo job `smoke` no workflow CI.
- `integration.sh`: script de teste de integração executado pelo job `integration` no workflow CI.
- `lint.sh`: script de lint executado pelo job `lint` no workflow CI.
- `validate_snapshots.sh`: valida os snapshots gravados em `snapshots/` comparando checksums com o manifest (`snapshots/checksums.json`). O script imprime diferenças encontradas (arquivos faltantes, checksums divergentes) e retorna código de saída não-zero em caso de falha. Executar localmente:

```bash
./tests/ci/validate_snapshots.sh
# Dependências: Python 3.12+ (para utilitários do projeto); não requer serviços externos.
```

No workflow CI, este script é invocado pelo job `validate-snapshots`.

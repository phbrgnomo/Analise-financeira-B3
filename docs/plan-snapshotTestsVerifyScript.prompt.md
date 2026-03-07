Plano: T5 — Testes de Snapshot & scripts/verify_snapshot.py

CRÍTICO: Crie o branch `feature/verify-snapshot` e implemente as seguintes mudanças para mitigar riscos de concorrência com SQLite e validar a robustez do sistema:


Objetivo
- Garantir verificação confiável e testável de snapshots existentes usando os utilitários já presentes no repositório.

Contexto
- Reutilizar `src/utils/checksums.py`, `src/etl/snapshot.py`, `scripts/validate_snapshots.py` e o wrapper `scripts/verify_snapshot.py`.
- Testes existentes: `tests/e2e/test_acceptance_snapshot.py`, `tests/integration/test_quickstart_mocked.py`, `tests/test_checksums.py`, `tests/test_integration_e2e_checksum.py`.

Critério de aceitação
- Testes novos passam 100% localmente.
- `scripts/verify_snapshot.py` retorna 0 quando snapshots batem com `snapshots/checksums.json`.
- Documentação curta adicionada em `docs/implementation-artifacts/snapshot-verification.md`.

Passos (ETA: 2 dias)
1) Revisar artefatos-chave
- Confirmar comportamento de `serialize_df_bytes`, `write_snapshot` e `save_raw_csv` para garantir serialização determinística.
- Confirmar formato e localização de `snapshots/checksums.json`.

2) Garantir gerador determinístico para testes
- Implementar/usar fixture que invoque gerador com TS controlado (`--ts` ou variáveis de ambiente) para produzir nomes previsíveis.
- Preferir `tmp_path` para isolamento.

3) Escrever/ajustar teste E2E determinístico
- Atualizar `tests/e2e/test_acceptance_snapshot.py` para usar o gerador determinístico e chamar:
  `python scripts/verify_snapshot.py --dir <tmp> --manifest snapshots/checksums.json`
- Assert: retorno 0; em caso contrário imprimir stdout/stderr para debug.

4) Adicionar testes unitários para CLI
- Novo `tests/test_validate_snapshots_cli.py` cobrindo:
  - `--update` escreve o manifest no local esperado
  - validação de remap (`--allow-external`) e caso de colisão de basename
  - chamadas de erro (caminhos inválidos)
- Usar `tmp_path` e invocar `python scripts/validate_snapshots.py` via `subprocess.run`.

5) Hardening/ajustes mínimos no CLI (se necessário)
- Garantir que `scripts/verify_snapshot.py` encontre `scripts/validate_snapshots.py` em execuções locais/CI.
- Evitar prints ruidosos que impossibilitem parser de saída em testes; preferir mensagens claras e códigos de saída documentados (0 ok, 2 diffs, 3 erro crítico).

6) Documentação curta
- Criar `docs/implementation-artifacts/snapshot-verification.md` com comandos:
  - `poetry install`
  - `python scripts/validate_snapshots.py --dir snapshots --manifest snapshots/checksums.json`
  - `python scripts/validate_snapshots.py --dir <tmp> --manifest <tmp_manifest> --update`
- Notas sobre determinismo (usar `--ts` / `tmp_path`) e `--allow-external`.

7) Verificação final local
- Executar:
  ```bash
  poetry install
  poetry run pytest -q tests/e2e/test_acceptance_snapshot.py::test_acceptance_snapshot
  poetry run pytest -q tests/test_validate_snapshots_cli.py
  ```
- Ajustar conforme necessário até testes passarem.

Decisões e convenções
- Reutilizar `scripts/validate_snapshots.py` e `scripts/verify_snapshot.py` (menor risco).
- Testes E2E devem injetar TS/nome fixo para evitar flakiness.
- `--allow-external` só para casos controlados; CI deve preferir trabalhar com `snapshots/` interno.
- Colisões de basename devem falhar com instrução clara; documentar solução.

Próximo passo
- Gerar patch/local files para: teste E2E ajustado, novo teste CLI e documentação em `docs/implementation-artifacts/` para revisão.

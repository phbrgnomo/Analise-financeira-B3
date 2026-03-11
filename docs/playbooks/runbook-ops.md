# Runbook de Operações

Este runbook consolida comandos importantes para gestão de snapshots, retenção,
restauração e validação. Ele serve como guia rápido para operadores e desenvolvedores
envolvendo processos críticos de produção.

## Gerar e validar snapshot localmente

### Aplicar migrações

Use o utilitário `scripts/apply_migrations.py` para garantir que o banco
esteja no schema correto antes de executar comandos que dependem dele.

```bash
python scripts/apply_migrations.py
```

## Gerar e validar snapshot localmente

```bash
# gerar um snapshot para PETR4 usando pipeline
poetry run main pipeline snapshot --ticker PETR4

# calcular checksum e garantir que o arquivo sidecar existe
sha256sum snapshots/PETR4_snapshot.csv
ls -l snapshots/PETR4_snapshot.csv.checksum
```

## Validar checksums em CI

O workflow `.github/workflows/checks-snapshots.yml` já lida com validações automáticas.
Para reproduzir localmente:

```bash
# simular o job de CI
python scripts/generate_ci_snapshot.py --dir tmp_snapshots/snapshots_test
python scripts/validate_snapshots.py --dir tmp_snapshots/snapshots_test --manifest snapshots/checksums.json
```

## Purge / retenção de snapshots

Uso geral:

```bash
# mostrar candidatos elegíveis para purge (dry-run)
poetry run main snapshots purge --older-than 90 --dry-run

# executar purge real com confirmação
poetry run main snapshots purge --older-than 90 --confirm

# arquivar em vez de deletar
poetry run main snapshots purge --older-than 365 --confirm --archive-dir snapshots/archive
```

A política padrão lê a variável `SNAPSHOT_RETENTION_POLICY` (JSON/YAML) ou usa
valores embutidos: `daily_keep_days=90`, `keep_monthly=12`, `keep_yearly=7`.

## Restore / verificação de snapshot

Para verificar que um snapshot pode ser restaurado com integridade:

```bash
poetry run main pipeline restore-verify --snapshot snapshots/PETR4_snapshot.csv
```

O comando devolve código de saída `0` (OK), `1` (aviso) ou `2` (falha). Ele cria
um banco temporário em memória e compara row counts e checksums.

## Scripts auxiliares

- `scripts/ci_validate_checksums.py` — utilitário CLI usado pelo job CI.
- `scripts/generate_ci_snapshot.py` — gera snapshots determinísticos para testes.
- `scripts/validate_snapshots.py` — compara diretório contra `snapshots/checksums.json`.
- `scripts/init_ingest_db.py` — inicializa banco SQLite com migrations.

## Contato e procedimentos de emergência

1. Se um snapshot crítico estiver corrompido, recupere a partir de um backup ou peça
o mantenedor do repositório para regenerar usando o histórico de dados brutos.
2. Use `snapshots purge --dry-run` antes de qualquer exclusão em produção.
3. Para auditoria, consulte a tabela `snapshots` no DB e `metadata/ingest_logs.jsonl`.

Referências: `docs/playbooks/story-close-checklist.md`, `docs/implementation-artifacts`

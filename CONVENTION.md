# Convenções de Nomes e Localização de Artefatos

Este documento formaliza as convenções de nomes e locais para snapshots, checksums e logs gerados pelo pipeline.

## 1. Snapshot CSV

### Convenção de nome de arquivo

- **Formato canônico**: `<TICKER>-YYYYMMDD.csv`
  - `TICKER` deve ser em maiúsculas, no formato B3 (ex.: `PETR4`, `ITUB3`, `BOVA11`).
  - `YYYYMMDD` corresponde à data de geração do snapshot (UTC).

**Exemplo:**
- `snapshots/PETR4-20260215.csv`

### Snapshot companion checksum

Para cada snapshot gerado, deve existir um arquivo `*.checksum` ao lado, contendo o checksum SHA256 do conteúdo do CSV.

- **Nome**: `<TICKER>-YYYYMMDD.csv.checksum`
- **Formato**: texto simples com o hash hex (uma linha).

**Exemplo:**
- `snapshots/PETR4-20260215.csv.checksum`

## 2. Localização dos artifacts

- **Snapshots**: `snapshots/`
- **Checksums**: no mesmo diretório, ao lado do snapshot
- **Logs de ingestão (metadata)**: `metadata/ingest_logs.jsonl` (append-only)

## 3. Legado e transição

Alguns artefatos legados podem usar nomes anteriores como `PETR4_snapshot.csv` ou `PETR4-20260215_snapshot.csv`. Para compatibilidade, o sistema deve aceitar estes formatos ao ler snapshots antigos, mas novos snapshots devem ser gerados no formato canônico acima.

Uma ferramenta de migração pode ser adicionada em `scripts/` para renomear snapshots legados e gerar `.checksum` correspondentes.

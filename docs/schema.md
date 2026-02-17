# Esquema Canônico de Snapshots

Este documento descreve o `schema.yaml` canônico usado para snapshots CSV gerados pelo pipeline.

Resumo:

- Arquivo de referência: `docs/schema.yaml`
- Versão inicial: `schema_version: 1`
- Objetivo: fornecer contrato estável para consumidores (notebooks, métricas, exportações)

Campos principais e significado:

- `ticker` (string): símbolo do ativo, ex.: PETR4.SA
- `date` (YYYY-MM-DD): data da observação; armazenar no formato ISO (sem hora)
- `open`, `high`, `low`, `close`, `adj_close` (numérico): preços do dia
- `volume` (integer): volume negociado
- `source` (string): provedor/source do dado (ex.: `yfinance`)
- `fetched_at` (datetime ISO8601 UTC): quando os dados foram buscados
- `raw_checksum` (string, opcional): SHA256 do payload bruto usado para auditoria

Exemplo de uso e local de exemplos

- Exemplo CSV de referência: `dados/examples/ticker_example.csv`
- Documento explicativo de schema: `docs/schema.md` (este arquivo)

Versionamento e migrações

- `schema_version` no `docs/schema.yaml` indica versão do contrato.
- Mudanças NÃO breaking (ex.: adicionar coluna opcional) → incrementa minor, documentar em `docs/schema.md`.
- Mudanças breaking (ex.: renomear coluna) → bump major `schema_version`, adicionar migration notes e atualizar processos de ingest/mapper.

Recomendações técnicas

- Validação: usar `pandera` para validar DataFrames no pipeline de canonical mapper.
- Testes: incluir teste que valida `dados/examples/ticker_example.csv` contra `docs/schema.yaml` em `tests/test_schema.py`.
- Snapshot metadata: incluir `schema_version` no metadado gravado junto com snapshot (ex.: em `snapshots/<file>.metadata.json` ou tabela `snapshots`).

Migração de esquema (procedimento sugerido):

1. Propor mudança e documentar em `docs/schema.md` com exemplos antes da alteração.
2. Atualizar `docs/schema.yaml` e incrementar `schema_version`.
3. Adicionar script de migração (se necessário) ou documentar como consumidores devem adaptar.
4. Rodar CI que valida snapshots com o novo schema e publicar notas de versão.

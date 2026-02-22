# Contrato de Metadados do Pipeline

Além do esquema de colunas para snapshots, o pipeline deve sempre gerar um arquivo de metadados (JSON) adjunto com o snapshot. Este contrato descreve os campos mínimos que devem existir para que ferramentas downstream (CI, validação, notebooks) processem o snapshot de forma confiável.

Campos obrigatórios

- `ticker` (string): símbolo do ativo, ex.: `PETR4.SA`
- `snapshot_date` (string): data do snapshot no formato `YYYY-MM-DD`
- `rows` (integer): número de linhas no snapshot (>= 0)
- `checksum` (string): SHA256 hex (64 caracteres)
- `schema_version` (string): versão do esquema no formato semver, ex.: `1.0.0`
- `source` (string): fonte dos dados, ex.: `yfinance`

Campos recomendados

- `snapshot_version` (integer)
- `notes` (string)
- `generated_by` (string)
- `rows_summary` (object): estatísticas resumidas (min_date, max_date, count)

Formato e validação

- Fornecemos um JSON Schema para validação em `docs/metadata_schema.json`.
- O projeto inclui `scripts/validate_metadata.py` que valida um arquivo de metadados contra o schema e aplica checagens extras (formato de data, checksum length).

Exemplo mínimo (JSON)

```json
{
  "ticker": "PETR4.SA",
  "snapshot_date": "2026-02-21",
  "rows": 1234,
  "checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "schema_version": "1.0.0",
  "source": "yfinance"
}
```

Como validar

```bash
python3 scripts/validate_metadata.py examples/metadata/petr4_snapshot.json
```

Notas

- O contrato é voltado para snapshots de dados tabulares gerados pelo pipeline. Para metadados de ingestão (logs), mantenha o arquivo `metadata/ingest_logs.json` (array) conforme implementação atual.
- Se for necessário estender o contrato, incremente `schema_version` e registre a compatibilidade.

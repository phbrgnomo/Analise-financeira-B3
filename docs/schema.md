# Esquema Canônico (schema_version: 1)

Este documento descreve o esquema canônico usado para snapshots CSV. Use `docs/schema.yaml` como fonte de verdade.

Campos:
- ticker (string, não-nulo): símbolo do ativo (ex: PETR4.SA)
- date (date, não-nulo): data da cotação no formato YYYY-MM-DD
- open/high/low/close/adj_close (float, nulos permitidos): preços
- volume (int, nulo permitido): volume negociado
- source (string, não-nulo): origem dos dados (ex: 'yahoo')
- fetched_at (datetime, não-nulo): timestamp UTC ISO8601 de coleta
- raw_checksum (string, não-nulo): SHA256 hexdigest do payload original (CSV ou provider payload)

Versionamento:
- `schema_version` em `docs/schema.yaml` identifica mudanças.
- Mudanças 'minor' (adição de colunas opcionais, comentários) -> incrementar versão minor.
- Mudanças 'breaking' (remoção/renomeação de colunas obrigatórias, troca de tipos) -> incrementar major e seguir processo de migração.

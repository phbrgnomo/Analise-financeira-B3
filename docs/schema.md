# Esquema Canônico (schema_version: 2)

Este documento descreve o esquema canônico usado para snapshots CSV. Use `docs/schema.json` como fonte de verdade.

Campos:
- ticker (string, não-nulo): símbolo do ativo (ex: PETR4.SA)
- date (date, não-nulo): data da cotação no formato YYYY-MM-DD
- open/high/low/close (float, nulos permitidos): preços
- volume (int, nulo permitido): volume negociado
- source (string, não-nulo): origem dos dados (ex: 'yahoo')
- fetched_at (datetime, não-nulo): timestamp UTC ISO8601 de coleta
- raw_checksum (string, não-nulo): SHA256 hexdigest do payload original (CSV ou provider payload)

- Observação: `adj_close` pode aparecer na saída do mapper para uso em cálculos internos (ex.: retornos), porém POR DECISÃO DE PROJETO **não é persistido** na forma CSV/DB por padrão.

	O arquivo `docs/schema.json` é a fonte de verdade do esquema persistido. Se for necessário persistir `adj_close` no futuro, atualize `docs/schema.json` e siga o processo de versionamento/migração descrito abaixo.

Versionamento:
- `schema_version` em `docs/schema.json` identifica mudanças.
- Mudanças 'minor' (adição de colunas opcionais, comentários) -> incrementar versão minor.
- Mudanças 'breaking' (remoção/renomeação de colunas obrigatórias, troca de tipos) -> incrementar major e seguir processo de migração.

Política de Versionamento e Migração
---
- `docs/schema.json` é a fonte de verdade. Sempre atualize `schema_version` quando alterar o esquema.
- Convenção recomendada: usar SemVer-like (major.minor), mas o campo atual é inteiro; incremente para indicar nova versão canônica do esquema.
- Para mudanças não-break (ex.: adicionar coluna opcional): incrementar a versão e documentar em `metadata.migrations`.
- Para mudanças breaking (ex.: renomear/remover coluna obrigatória):
	1. Atualize `docs/schema.json` com nova `schema_version` e adicione uma entrada em `metadata.migrations` descrevendo a mudança.
 2. Implementar código de migração (script SQL ou função Python) que atualize bancos existentes — colocar em `scripts/`.
 3. Atualizar `src/db.py` (se necessário) para aceitar múltiplas versões de schema (ou aplicar migração antes de conectar).
 4. Atualizar testes e snapshots, e rodar full `pytest`.

Recomendações operacionais
---
- Ao aplicar mudanças no esquema em ambiente de produção:
	- Faça backup do arquivo de dados (`dados/data.db`).
	- Teste migrações em um clone do DB antes de executar em produção.
	- Aplique `VACUUM` e verifique permissões (`chmod 600 dados/data.db`) após migração.

Exemplo de processo (renomear coluna `close` → `adj_close` - breaking):
1. Criar migração `scripts/migrations/2026-02-23-rename-close-to-adj_close.sql` que:
	 - adiciona nova coluna `adj_close`, copia valores de `close` para `adj_close`, e - opcionalmente - remove `close` após validação.
2. Atualizar `docs/schema.json` com `schema_version` incrementado e entrada de migração explicando o passo-a-passo.
3. Atualizar `src/db.py` para suportar ambos os nomes (compatibilidade) ou garantir que a migração foi aplicada antes do app abrir conexões.

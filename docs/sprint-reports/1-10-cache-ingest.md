---
title: "Story 1.10 — Cache de Snapshots e Ingestão Incremental"
date: 2026-02-26
story: 1-10-cache-de-snapshots-e-ingestao-incremental
author: Amelia (Dev Agent)
---

# Sprint Report — Story 1.10: Cache de Snapshots e Ingestão Incremental

Resumo
-------
A entrega introduz um mecanismo de cache para arquivos de snapshot e um fluxo
integrado de ingestão incremental que evita reprocessamento de dados
idênticos. O pipeline agora grava snapshots versionados em `dados/snapshots`,
calcula e verifica checksums SHA256, mantém metadados no banco e só persiste
linhas novas ou alteradas usando o helper `ingest_from_snapshot`.

Além disso, foi adicionada uma CLI `ingest-snapshot` com flags para `--force-`
refresh, TTL configurável e cache-file personalizável; essa rotina é usada no
fluxo principal em `src/main._fetch_and_prepare_asset` quando ingestindo preços.

Decisões principais e justificativa
-----------------------------------

- **Cache simples em JSON**: um arquivo (`SNAPSHOT_CACHE_FILE`) armazena chaves
  por caminho absoluto e checksum/processed_at. TTL lido de `SNAPSHOT_TTL`.
  Justificativa: evita dependências externas e é suficiente para uso local.

- **TTL e force-refresh**: TTL configurável e flag `FORCE_REFRESH` permitem
  controle fino e testes determinísticos. Forçar refresh útil em debugging e
  reprocessamento manual.

- **Checksum determinístico**: serialização de DataFrame em bytes ordenados
  garante checksum reprodutível; comparado ao `.checksum` file quando presente.

- **Incremental ingest**: diferenças entre DataFrame corrente e dados canônicos
  são calculadas por índice de datas e `raw_checksum` para detectar mudanças.
  Apenas linhas novas/alteradas são escritas via `db.write_prices`.

- **Helper reutilizável**: função pública `ingest_from_snapshot` usada tanto no
  CLI quanto no pipeline principal, facilitando testes e isolamento.

- **Logs estruturados**: mensagens de INFO documentam cache hits/reações e
  contagem de linhas processadas; warnings quando gravação de metadados falha.

Implementação (arquivos alterados)
----------------------------------

- `src/ingest/pipeline.py` (significativa)
  - adicionados vários helpers de snapshot e cache; função principal
    `ingest_from_snapshot` com lógica de TTL/force/cache, escrita de
    metadados no DB, diff incremental e chamada a `db.write_prices`.

- `src/ingest.py` (novo)
  - orquestra camada de alto nível usada pela CLI; possui lógica de normalização,
    leitura de CSV, cache JSON e cálculo de mudanças (usando abstração `DatabaseClient`).

- `src/ingest/cache.py` (novo)
  - utilitários para carregar/gravar o cache e verificar frescor de entradas.

- `src/main.py`
  - integração do helper `ingest_from_snapshot` no processo de ingest;
    novo comando Typer `ingest-snapshot` e opções associadas.

- `tests/test_ingest_cache_incremental.py` (novo)
  - testes unitários para `ingest_from_snapshot`: cache hits, mudanças e
    ingest incremental.

- `tests/test_ingest_snapshot.py` (novo)
  - testes de integração leve usando CSVs temporários e DB em memória
    para cobrir cache, TTL, force-refresh e ingest incremental.

- `tests/test_cli.py` atualizado com verificações das novas opções/flags CLI.

- README.md atualizado com instruções de env vars e descrição do comando CLI.

Testes e verificação
--------------------

- Suíte completa rodou localmente com `poetry run pytest -q` (toda a suíte de
  testes, incluindo os novos casos de ingestão, passou sem falhas).
- Novos testes cobrem casos principais e funcionam em modo "playback" de redes
  (independente de chamadas externas).
- Pipelines de CI atuais também passaram; o novo arquivo de testes não altera a
  matriz existente.

Compatibilidade e riscos conhecidos
----------------------------------

- A lógica de cache assume que apenas um processo escreve no arquivo JSON; se
  houver concorrência (ex.: vários workers ingestindo simultaneamente), há um
  risco de corrida. Mitigação: o cache é simples e pode ser substituído por
  Redis mais tarde; threads geralmente não usadas.

- A serialização de DataFrame usada para checksum precisa ser determinística;
  mudanças futuras em pandas ou na função `serialize_df_bytes` podem alterar
  valores e causar reprocessamentos inesperados, mas isso não afeta
  integridade dos dados, apenas a cache.

Próximos passos recomendados
---------------------------

1. Preparar workflow CI agendado de smoke tests que chame `ingest-snapshot`
   sobre alguns arquivos canários (dry-run ou temporários).
2. Documentar convenções de snapshot em `docs/` e conectar com funcionalidades
   planejadas da épica 2 (snapshot exportação/purge).
3. Considerar adicionar métricas Prometheus para contadores de linhas
   processadas/ignored na rotina de ingest.

Como validar manualmente (comandos)
----------------------------------

1. Executar comando na linha de comando (dry-run de ingest com snapshot de
   exemplo):

```bash
poetry run python -m src.main ingest-snapshot examples/sample_snapshot.csv --ttl 0
```

2. Reexecutar para verificar `cached=True` e `processed_rows=0`.

3. Alterar uma linha do snapshot e reexecutar para ver `processed_rows` > 0.

4. Usar `FORCE_REFRESH=1` para forçar reprocessamento independentemente do cache.

📌 Exemplo de uso no pipeline:

```python
from src.ingest.pipeline import ingest_from_snapshot
r = ingest_from_snapshot(df, "PETR4.SA")
```

Registro de alterações (resumo)
-------------------------------

- Feature implementada na branch `dev-story-1-10`, testada localmente e
  documentada; PR a ser aberto/mergeado.

---

Fim do relatório.

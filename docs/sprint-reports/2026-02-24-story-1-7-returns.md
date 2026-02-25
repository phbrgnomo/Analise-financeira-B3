---
title: "Story 1.7 — Transformação de retornos e persistência em returns"
date: 2026-02-24
story: 1-7-implementar-transformacao-de-retornos-e-persistencia-em-returns
author: Amelia (Dev Agent)
---

# Sprint Report — Story 1.7: Transformação de retornos e persistência

Resumo
-------
Esta entrega implementa a rotina `compute_returns()` para calcular retornos diários
simples a partir da tabela `prices` e persistir no banco de dados na tabela
`returns`. Inclui garantias de idempotência (upsert), telemetria mínima, testes
unitários e uma pequena documentação com convenções de anualização.

Decisões principais e racional
------------------------------

- Leitura via camada de DB (`db.read_prices`) — Racional: manter contrato comum
  de acesso a dados do projeto. Evita duplicação de lógica SQL e garante que
  filtros/colunas canônicas sejam centralizados no `src.db`.

- Preferência por coluna ajustada (`adj_close`) quando disponível — Racional:
  retornos devem usar preços ajustados a splits/dividendos quando possível para
  evitar viés em séries históricas. Implementação faz fallback para `close`.

- Upsert com `ON CONFLICT(...) DO UPDATE` quando suportado, fallback para
  `INSERT OR REPLACE` — Racional: `ON CONFLICT` permite atualizar campos
  seletivamente (preservando `created_at` quando apropriado). `INSERT OR
  REPLACE` sobrescreve a linha inteira e pode perder metadados; por isso é
  usado apenas em runtimes antigos do SQLite.

- Preservar/registrar `created_at` e telemetria (job_id, rows_written,
  duration_ms) — Racional: observabilidade mínima para auditoria e reexecução
  segura e para facilitar investigação em caso de divergências.

- Usar datetimes timezone-aware (`datetime.now(timezone.utc)`) — Racional:
  consistência em persistência de timestamps e evitar advertências/bugs
  relacionados a timezone; mantém compatibilidade com `src.db` que grava
  timestamps em ISO UTC.

- Centralizar convenção de anualização (`TRADING_DAYS = 252`) — Racional:
  evitar valores mágicos espalhados; garante que conversões de risco/retorno
  usem a mesma base em todo o código e testes.

Implementação (arquivos alterados)
---------------------------------

- `src/retorno.py`
  - Implementação de `compute_returns()` usando `db.read_prices`.
  - Adicionada constante `TRADING_DAYS` e mudança para datetimes timezone-aware.

- `src/db.py`
  - `write_returns()` agora tenta usar `ON CONFLICT(ticker,date,return_type)
    DO UPDATE` quando a versão do SQLite suportar; fallback para
    `INSERT OR REPLACE` para compatibilidade.

- `src/main.py`
  - CLI `compute-returns` existente segue delegando para `compute_returns`; uso
    de `TRADING_DAYS` para relatórios de annualização.

- `tests/test_returns.py` (existente)
  - Testes executados e confirmados: happy path, idempotência (re-run sem
    duplicação), e comportamento com `start`/`end` range.

- `docs/implementation-artifacts/retornos-conventions.md`
  - Nova documentação curta com convenções de anualização, esquema `returns`
    e exemplo de SQL de upsert.

Testes e verificação
--------------------

- Testes locais executados:
  - `pytest tests/test_returns.py` — passou (todos os testes do arquivo).
  - Suíte completa `poetry run pytest` — passou (98 passed, 21 warnings no
    ambiente local de desenvolvimento).

- Warnings menores foram resolvidos (uso de `datetime.utcnow()` substituído).

Compatibilidade e riscos conhecidos
----------------------------------

- SQL runtime: a query `ON CONFLICT ... DO UPDATE` depende de SQLite >= 3.24.0
  — código detecta a versão e aplica fallback automaticamente, porém ambientes
  muito antigos perderão o comportamento de preservação seletiva de campos.

- `INSERT OR REPLACE` sobrescreve a linha inteira; se a aplicação depender de
  campos adicionais não cobertos pela rotina de retorno, esses campos podem ser
  perdidos no fallback. Recomenda-se atualizar runtime SQLite quando possível.

- Limitações: a rotina assume que `db.read_prices` devolve colunas com nomes
  canônicos; se a ingestão futura mudar o esquema canônico será necessário
  adaptar `compute_returns` ou a camada de DB.

Próximos passos recomendados
---------------------------

1. Revisar/expandir documentação em `docs/` para incluir exemplos de consulta
   e pipelines de consumidor (notebooks que usam `returns`).
2. Adicionar métricas/time-series (Prometheus/Influx) se for necessário monitorar
   rota de ingest em produção. Hoje gravamos apenas snapshots JSON local.
3. Migrar outros pontos do repositório para uso de timezone-aware (se houver
   mais) e centralizar helpers de tempo (ex.: `src/time_utils.py`).

Como validar manualmente (comandos)
----------------------------------

1. Rodar CLI para um ticker de teste (dry-run):

```bash
poetry run python -m src.main compute-returns --ticker PETR4.SA --dry-run
```

2. Persistir e inspecionar DB (SQLite):

```bash
# executar sem --dry-run e então abrir o DB
poetry run python -m src.main compute-returns --ticker PETR4.SA
sqlite3 dados/data.db "SELECT ticker, date, \"return\" FROM returns WHERE ticker='PETR4.SA' ORDER BY date LIMIT 5;"
```

3. Revisar PR com mudanças: https://github.com/phbrgnomo/Analise-financeira-B3/pull/188

Registro de alterações (resumo)
-------------------------------

- Correções de implementação e docs para story 1-7 aplicadas em branch
  `dev-story-1-7` e empurradas para o repositório remoto; PR criado (#188).

Fim do relatório.

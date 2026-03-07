## Diagrama do Fluxo de Dados

**Legenda curta**

- **Coleta:** adapters e scripts buscam dados externos e salvam CSVs em `raw/` ou `snapshots/`.
- **Validação:** checagem de formato e checksums; entradas inválidas são rejeitadas.
- **ETL:** pipeline transforma e enriquece os dados (normalização, tipos, cálculos).
- **Persistência:** gravação idempotente em SQLite via `src/db_client.py` e migrations em `migrations/`.
- **Orquestração:** CLI e testes acionam e validam o fluxo.
- **Saída:** métricas, relatórios e artefatos gerados em `outputs/` e `reports/`.

---

```mermaid
flowchart TB
  CLI[CLI: src/main.py + src/pipeline.py] --> ORQ[Orquestrador: src/ingest/pipeline.py]

  subgraph Coleta
    ORQ --> FAC[Factory: src/adapters/factory.py]
    FAC --> ADP[Adapter: src/adapters/yfinance_adapter.py]
    ADP --> RAW[Raw CSV + checksum: src/ingest/raw_storage.py]
  end

  subgraph Transformacao
    ADP --> MAP[Mapper: src/etl/mapper.py]
    MAP --> VAL[Schema: docs/schema.json + pandera]
  end

  subgraph Persistencia
    VAL --> SNAP[Snapshot/TTL: src/ingest/snapshot_ingest.py]
    SNAP --> DIFF[Diff incremental: rows_to_ingest\nsrc/ingest/snapshot_ingest.py]
    DIFF --> UPSERT[Upsert prices: src/db/prices.py\nPK ticker+date]
  end

  subgraph PosProcessamento
    UPSERT --> RET[Retornos: src/retorno.py]
    RET --> MET[Métricas/logs: src/metrics.py + src/logging_config.py]
  end

  RAW --> AUD[Metadata JSONL: metadata/ingest_logs.jsonl]
  UPSERT --> DB[(SQLite: dados/data.db)]
  RET --> DB
```

---

## Sequência Temporal (Ingestão)

```mermaid
sequenceDiagram
  autonumber
  participant CLI as CLI (src/main.py / src/pipeline.py)
  participant PL as Ingest Pipeline (src/ingest/pipeline.py)
  participant AF as Adapter Factory (src/adapters/factory.py)
  participant AD as Adapter (src/adapters/yfinance_adapter.py)
  participant MP as Mapper (src/etl/mapper.py)
  participant RS as Raw Storage (src/ingest/raw_storage.py)
  participant SI as Snapshot Ingest (src/ingest/snapshot_ingest.py)
  participant DB as SQLite (dados/data.db)
  participant RT as Retorno (src/retorno.py)
  participant MT as Métricas/Logs (src/metrics.py)

  CLI->>PL: ingest_command()/ingest()
  PL->>AF: get_adapter(source)
  AF-->>PL: adapter
  PL->>AD: fetch(ticker)
  AD-->>PL: DataFrame bruto

  PL->>MP: to_canonical(df, source, ticker)
  MP-->>PL: DataFrame canônico + checksum

  alt dry_run
    PL-->>CLI: status=success (sem escrita)
  else ingest real
    PL->>RS: save_raw_csv(df bruto)
    RS-->>PL: path + checksum + metadata

    PL->>SI: ingest_from_snapshot(df canônico, ticker)
    SI->>DB: get_last_snapshot_payload/read_prices
    SI->>SI: cache TTL + diff incremental
    SI->>DB: write_prices (upsert)
    SI-->>PL: rows_processed + cached

    PL->>RT: compute_returns(ticker)
    RT->>DB: read_prices + write_returns
    RT-->>PL: retornos persistidos

    PL->>MT: logging + increment_counter/observe_histogram
    PL-->>CLI: status final + job_id
  end
```

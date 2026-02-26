Guia rápido — como calcular retornos e usar o `compute-returns`

Este documento mostra comandos e exemplos de como usar o CLI para calcular
retornos, executar em modo `dry-run` e consultar resultados no banco local.

Comando básico (dry-run — não persiste):

```bash
poetry run python -m src.main compute-returns --ticker PETR4.SA --dry-run
```

Comando persistente (persiste no DB configurado):

```bash
poetry run python -m src.main compute-returns --ticker PETR4.SA
```

Exemplo: consultar retornos via sqlite3/SQL

```sql
SELECT date, return, created_at
FROM returns
WHERE ticker = 'PETR4.SA'
ORDER BY date DESC
LIMIT 10;
```

Notas importantes
- O banco embutido é `dados/data.db` por padrão; você pode usar `src.db.connect`
  ou override via `DB_PATH` quando necessário.
- O comportamento de upsert depende da versão do SQLite: o projeto implementa
  um fallback transacional para preservar `created_at` em runtimes antigos.
- Para testes locais, há fixtures em `tests/fixtures` e snapshots em `snapshots/`.

Smoke tests e CI
- Há um workflow agendado que executa um `--dry-run` diariamente: [/.github/workflows/compute-returns-smoke.yml](/.github/workflows/compute-returns-smoke.yml)
- Há também uma matriz de compatibilidade SQLite: [/.github/workflows/sqlite-compat.yml](/.github/workflows/sqlite-compat.yml)

Exemplo rápido para rodar localmente com DB temporário (Linux/macOS):

```bash
# cria venv + deps
poetry install

# rodar dry-run
poetry run python -m src.main compute-returns --ticker PETR4.SA --dry-run

# rodar persistente
poetry run python -m src.main compute-returns --ticker PETR4.SA
```

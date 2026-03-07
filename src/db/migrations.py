"""Online migrations for the db package.

Provides idempotent helpers that adjust column affinities (TEXT → DATE) for
the ``prices`` and ``returns`` tables.  Migrations are guarded by
``PRAGMA user_version`` and run at most once per database file.
"""

import sqlite3

from src.db._helpers import _quote_identifier
from src.db.schema import _load_canonical_schema, _sql_type


def _migrate_prices_date_column(conn: sqlite3.Connection) -> None:
    """Garante afinidade DATE para `prices.date` de forma idempotente.

    O processo de migração é relativamente custoso pois recria e copia
    completamente a tabela.  Para evitar que isto seja executado em cada
    nova conexão (especialmente em bancos maiores), marcamos um
    indicador de migração usando ``PRAGMA user_version``.  A migração
    será tentada no máximo uma vez por banco; após ela ser concluída
    com sucesso (ou detectarmos que já está em formato DATE) bumpamos o
    valor de ``user_version`` para 1 para curar chamadas futuras.

    Observação: o chamador decidiu não invocar esta função quando o
    ``user_version`` já está >= 1, evitando a sobrecarga de `PRAGMA
    table_info` em cada validação de esquema (sourcery warning).
    """
    cur = conn.cursor()
    # já migrado? / já no formato esperado?
    cur.execute("PRAGMA user_version")
    version = cur.fetchone()[0] or 0
    if version >= 1:
        return

    cur.execute("PRAGMA table_info('prices')")
    info = cur.fetchall()
    if not info:
        # nada a migrar, mas sinalizamos que checamos
        cur.execute("PRAGMA user_version = 1")
        conn.commit()
        return

    existing_types = {row[1]: (row[2] or "").upper() for row in info}
    if existing_types.get("date") == "DATE":
        # já está no tipo correto, marca para não reexecutar
        cur.execute("PRAGMA user_version = 1")
        conn.commit()
        return

    required_cols = {"ticker", "date", "source", "raw_checksum", "fetched_at"}
    if not required_cols.issubset(set(existing_types.keys())):
        # esquema inesperado, aborta sem atualizar a versão para ser seguro
        return

    schema = _load_canonical_schema()
    schema_cols = [c["name"] for c in schema.get("columns", [])]
    col_defs = []
    for col in schema.get("columns", []):
        name = col["name"]
        typ = _sql_type(col.get("type", "string"))
        nullable = "" if col.get("nullable", True) else "NOT NULL"
        col_defs.append(f"{name} {typ} {nullable}".strip())

    create_sql = (
        "CREATE TABLE prices_tmp_date_migration ("
        + ", ".join(col_defs)
        + ", PRIMARY KEY (ticker, date))"
    )

    common_cols = [c for c in schema_cols if c in existing_types]
    if not common_cols:
        return
    cols_csv = ", ".join(common_cols)

    cur.execute(create_sql)
    cur.execute(
        f"INSERT OR REPLACE INTO prices_tmp_date_migration ({cols_csv}) "
        f"SELECT {cols_csv} FROM prices"
    )
    cur.execute("DROP TABLE prices")
    cur.execute("ALTER TABLE prices_tmp_date_migration RENAME TO prices")
    # marca migração como realizada
    cur.execute("PRAGMA user_version = 1")
    conn.commit()


def _migrate_returns_date_column(conn: sqlite3.Connection) -> None:
    """Garante afinidade DATE para `returns.date` de forma idempotente.

    Similarmente a :func:`_migrate_prices_date_column`, usamos
    ``PRAGMA user_version`` para evitar rodar a migração em cada nova
    conexão e um passo extra para eliminar eventuais tabelas temporárias
    deixadas por falhas anteriores.

    A versão **2** no ``user_version`` indica que tanto preços quanto
    retornos já foram migrados.  Caso o banco esteja em uma versão
    anterior, tentaremos atualizar apenas se a coluna ainda não tiver
    afinidade DATE; qualquer tabela ``returns_tmp_date_migration`` existente
    será descartada antes de começar.
    """
    cur = conn.cursor()

    # versão mínima necessária para pular a migração (1 era apenas preços)
    cur.execute("PRAGMA user_version")
    version = cur.fetchone()[0] or 0
    if version >= 2:
        return

    # limpar migração intermediária potencialmente deixada por execução
    # anterior falha, para que o CREATE TABLE não dê erro.
    cur.execute("DROP TABLE IF EXISTS returns_tmp_date_migration")

    cur.execute("PRAGMA table_info('returns')")
    info = cur.fetchall()
    if not info:
        # tabela inexistente; nada a fazer, mas não ajustamos a versão para
        # permitir a tentativa posterior caso a tabela seja criada depois.
        return

    existing_types = {row[1]: (row[2] or "").upper() for row in info}
    if existing_types.get("date") == "DATE":
        # já correto, marca versão para evitar rechecagens futuras
        cur.execute("PRAGMA user_version = 2")
        conn.commit()
        return

    # começamos uma transação explícita para que, em caso de erro, não
    # deixemos a tabela temporária flutuando.
    cur.execute("BEGIN")
    try:
        _recreate_returns_table_with_date_type(cur, conn)
    except Exception:
        conn.rollback()
        raise


def _recreate_returns_table_with_date_type(cur, conn):
    """Recria a tabela returns com coluna date tipada como DATE."""
    qt = _quote_identifier("ticker")
    qd = _quote_identifier("date")
    qr = _quote_identifier("return_value")
    qrt = _quote_identifier("return_type")
    qc = _quote_identifier("created_at")

    cur.execute(
        "CREATE TABLE returns_tmp_date_migration ("
        f"{qt} TEXT, "
        f"{qd} DATE, "
        f"{qr} REAL, "
        f"{qrt} TEXT, "
        f"{qc} TEXT, "
        f"UNIQUE({qt}, {qd}, {qrt})"
        ")"
    )
    cur.execute(
        "INSERT OR REPLACE INTO returns_tmp_date_migration "
        f"({qt}, {qd}, {qr}, {qrt}, {qc}) "
        f"SELECT {qt}, {qd}, {qr}, {qrt}, {qc} FROM returns"
    )
    cur.execute("DROP TABLE returns")
    cur.execute("ALTER TABLE returns_tmp_date_migration RENAME TO returns")
    # versão 2 sinaliza que migração de retornos também foi aplicada
    cur.execute("PRAGMA user_version = 2")
    conn.commit()

#!/usr/bin/env python3
"""Script de inicialização do banco de dados de ingest (dados/data.db).

Cria o arquivo .db e a tabela ingest_logs sem alterar o restante do pipeline.
Uso: python scripts/init_ingest_db.py --db dados/data.db
"""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
from pathlib import Path

from src.paths import DATA_DIR

logger = logging.getLogger(__name__)


def _normalize_input(p: str) -> tuple[str, bool]:
    """Normalize raw string input and return (normalized, is_abs)."""
    return (os.path.normpath(p), os.path.isabs(p))


def _ensure_absolute_within_data(
    real_path: str, *, error_suffix: str | None = None
) -> str:
    """Ensure an absolute real path is inside DATA_DIR, return canonical string.

    error_suffix can be provided by callers (e.g. CLI) to append contextual
    guidance such as flag-specific override instructions. When omitted a
    generic message without CLI-specific hints is used.
    """
    data_dir_str = str(Path(DATA_DIR).resolve())
    if error_suffix is None:
        error_suffix = ""
    elif error_suffix and not error_suffix.startswith(" "):
        error_suffix = f" {error_suffix}"

    try:
        common = os.path.commonpath([real_path, data_dir_str])
    except ValueError:
        base_msg = "Refusing to initialize database outside of DATA_DIR."
        raise ValueError(f"{base_msg}{error_suffix}") from None

    if common != data_dir_str:
        base_msg = "Refusing to initialize database outside of DATA_DIR."
        raise ValueError(f"{base_msg}{error_suffix}")

    return real_path


def _place_under_data_dir(rel_normalized: str) -> str:
    """Place a normalized relative path under DATA_DIR and return canonical string."""
    data_dir_str = str(Path(DATA_DIR).resolve())
    return os.path.join(data_dir_str, rel_normalized.lstrip(os.path.sep))


def init_db(db_path: Path | str | None = None, allow_external: bool = False) -> None:
    """Initialize the ingest SQLite database at `db_path`.

    Behavior:
    - Defaults to `DATA_DIR / "data.db"` when `db_path` is None.
    - When `allow_external` is False, only allows databases inside `DATA_DIR`.
    - Rejects null bytes and relative paths containing parent-traversal when
      `allow_external` is False.

    Raises ValueError for invalid or disallowed paths and propagates
    sqlite3.Error for database-level failures.
    """

    resolved_db = _resolve_db_path(db_path, allow_external)

    parent_dir = os.path.dirname(resolved_db)
    os.makedirs(parent_dir, exist_ok=True)

    try:
        with sqlite3.connect(resolved_db) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ingest_logs (
                    job_id TEXT PRIMARY KEY,
                    source TEXT,
                    fetched_at TEXT,
                    raw_checksum TEXT,
                    rows INTEGER,
                    filepath TEXT,
                    status TEXT,
                    error_message TEXT,
                    created_at TEXT
                );
                """
            )
    except sqlite3.Error as exc:
        logger.error("Failed to initialize ingest DB at %s: %s", resolved_db, exc)
        raise


def _resolve_db_path(db_path: Path | str | None, allow_external: bool) -> str:
    """Normalize and validate the requested DB path, returning a resolved path string.

    This centralizes path-safety checks so the logic is easier to test and
    reason about. When `allow_external` is False, relative paths are treated as
    relative to `DATA_DIR`; absolute paths must already be inside `DATA_DIR`.
    """
    # Delegate to smaller functions to reduce cyclomatic complexity
    if allow_external:
        return _resolve_db_path_allow_external(db_path)
    return _resolve_db_path_restricted(db_path)


def _resolve_db_path_allow_external(db_path: Path | str | None) -> str:
    """Resolve DB path when external paths are allowed.

    Accepts user-provided absolute or relative paths (after normalization).
    """
    if db_path is None:
        return str(Path(DATA_DIR) / "data.db")
    if isinstance(db_path, Path):
        try:
            return str(db_path.resolve())
        except Exception:
            return str(db_path.absolute())
    if isinstance(db_path, str):
        if "\x00" in db_path:
            raise ValueError("Invalid database path: contains null byte")
        return os.path.realpath(db_path)
    raise TypeError("db_path must be a str, pathlib.Path or None")


def _resolve_db_path_restricted(db_path: Path | str | None) -> str:
    """Resolve DB path when external paths are NOT allowed.

    Enforces that the final path is inside `DATA_DIR` and rejects traversal.
    """
    if db_path is None:
        return str(Path(DATA_DIR) / "data.db")

    # Determine candidate string from provided db_path
    candidate = _candidate_from_db_path(db_path)

    data_dir_resolved = str(Path(DATA_DIR).resolve())

    return _finalize_candidate_within_data(candidate, data_dir_resolved)


def _candidate_from_db_path(db_path: Path | str | None) -> str:
    """Return a candidate string for the db path or raise for invalid input."""
    if isinstance(db_path, Path):
        return str(db_path)
    if isinstance(db_path, str):
        if "\x00" in db_path:
            raise ValueError("Invalid database path: contains null byte")

        normalized, is_abs = _normalize_input(db_path)

        if is_abs:
            real = os.path.realpath(db_path)
            return _ensure_absolute_within_data(real)
        if ".." in normalized.split(os.path.sep):
            raise ValueError(
                (
                    "Relative paths containing '..' are not allowed when "
                    "--allow-external is False"
                )
            )
        return _place_under_data_dir(normalized)

    raise TypeError("db_path must be a str, pathlib.Path or None")


def _finalize_candidate_within_data(candidate: str, data_dir_resolved: str) -> str:
    """Ensure `candidate` is within `data_dir_resolved` and return a resolved path."""
    if os.path.isabs(candidate):
        try:
            resolved = os.path.realpath(candidate)
        except Exception:
            resolved = os.path.abspath(candidate)

        try:
            common = os.path.commonpath([resolved, data_dir_resolved])
        except ValueError:
            raise ValueError(
                "Refusing to initialize database outside of DATA_DIR. "
                "Pass --allow-external to override (use with caution)."
            ) from None
        if common != data_dir_resolved:
            raise ValueError(
                "Refusing to initialize database outside of DATA_DIR. "
                "Pass --allow-external to override (use with caution)."
            )
        return resolved

    if any(part == ".." for part in candidate.split(os.path.sep)):
        raise ValueError(
            (
                "Relative paths containing '..' are not allowed when "
                "--allow-external is False"
            )
        )

    return os.path.realpath(os.path.join(data_dir_resolved, candidate))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=("Inicializa o banco de ingest_logs"))

    parser.add_argument(
        "--db",
        default=str(DATA_DIR / "data.db"),
        help=("Caminho para o arquivo .db"),
    )
    parser.add_argument(
        "--allow-external",
        action="store_true",
        help=("Permite inicializar o banco fora de DATA_DIR (use com cuidado)"),
    )

    args = parser.parse_args()
    try:
        resolved = _resolve_db_path(args.db, args.allow_external)
    except (ValueError, TypeError) as exc:
        parser.error(str(exc))
    # `resolved` is already a validated, canonical absolute path.
    # We can bypass the restricted re-validation by telling `init_db` that
    # external paths are allowed for this call so it doesn't re-reject the
    # already-validated path.
    init_db(resolved, allow_external=True)
    print(f"Banco de ingest inicializado em: {resolved}")

#!/usr/bin/env python3
"""Gerador CI para criar o snapshot `PETR4_snapshot.csv` em um diretório alvo.

Usa a fixture `tests/fixtures/sample_snapshot.csv` e a função
`src.etl.snapshot.write_snapshot` para escrever o CSV com a
serialização canônica do projeto (determinística).

O destino padrão é `$SNAPSHOT_DIR` se definido, senão `$RUNNER_TEMP/snapshots_test`,
senão `./snapshots_test`.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Union

try:
    import pandas as pd
except Exception:  # pragma: no cover - runtime dependency
    print("Erro: pandas é necessário.", file=sys.stderr)
    raise


def _sanitize_env_value(val: str) -> str:
    """Remover bytes nulos e espaços acidentais de valores de ambiente."""
    if not isinstance(val, str):
        raise ValueError("Valor da variável de ambiente não é uma string")
    return val.split("\x00", 1)[0].strip()


def safe_path_under(base: Union[str, Path], user_value: str) -> Path:
    """
    Constrói um `Path` a partir de `user_value` e garante que o resultado
    esteja dentro de `base`. Lança `ValueError` se o caminho ficar fora.
    """
    base_path = Path(base).resolve()
    val = _sanitize_env_value(user_value)

    candidate = Path(val)
    if not candidate.is_absolute():
        candidate = base_path / candidate

    candidate = candidate.resolve()

    try:
        if not candidate.is_relative_to(base_path):
            raise ValueError("Caminho fora do diretório permitido")
    except AttributeError as _:
        import os as _os
        if _os.path.commonpath([str(base_path), str(candidate)]) != str(base_path):
            raise ValueError("Caminho fora do diretório permitido") from None

    return candidate


def choose_snapshot_dir(repo_root: Path) -> Path:
    """Decide e retorna o `snapshot_dir` preferido com validação básica.

    Prioridade: `SNAPSHOT_DIR` > `RUNNER_TEMP/snapshots_test` > repo_root/snapshots_test
    """
    snapshot_dir = None

    raw_snapshot_dir = os.environ.get("SNAPSHOT_DIR")
    if raw_snapshot_dir:
        try:
            snapshot_dir = safe_path_under(repo_root, raw_snapshot_dir)
        except ValueError as exc:
            msg = (
                "Aviso: variável SNAPSHOT_DIR inválida: "
                f"{exc}; usando fallback."
            )
            print(msg, file=sys.stderr)

    if snapshot_dir is None and os.environ.get("RUNNER_TEMP"):
        try:
            raw_runner = _sanitize_env_value(os.environ["RUNNER_TEMP"])
            system_tmp = Path(tempfile.gettempdir()).resolve()
            candidate = str(Path(raw_runner) / "snapshots_test")
            try:
                snapshot_dir = safe_path_under(system_tmp, candidate)
            except ValueError as exc:
                msg = (
                    "Aviso: RUNNER_TEMP inválido ou fora do diretório "
                    f"temporário: {exc}; usando fallback."
                )
                print(msg, file=sys.stderr)
        except Exception:
            print("Aviso: RUNNER_TEMP inválido; usando fallback.", file=sys.stderr)

    if snapshot_dir is None:
        snapshot_dir = repo_root / "snapshots_test"

    return snapshot_dir


def validate_snapshot_dir(snapshot_dir: Path, repo_root: Path) -> None:
    """Valida que `snapshot_dir` está dentro de `repo_root` ou do temp do sistema.

    Lança `ValueError` se inválido.
    """
    resolved_snapshot = snapshot_dir.resolve()
    allowed = False
    repo_resolved = repo_root.resolve()
    system_tmp = Path(tempfile.gettempdir()).resolve()
    try:
        if resolved_snapshot.is_relative_to(repo_resolved):
            allowed = True
    except AttributeError:
        import os as _os
        common = _os.path.commonpath([str(repo_resolved), str(resolved_snapshot)])
        if common == str(repo_resolved):
            allowed = True

    try:
        if resolved_snapshot.is_relative_to(system_tmp):
            allowed = True
    except AttributeError:
        import os as _os
        common = _os.path.commonpath([str(system_tmp), str(resolved_snapshot)])
        if common == str(system_tmp):
            allowed = True

    if not allowed:
        raise ValueError("Diretório de snapshot fora dos diretórios permitidos")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]

    # localizar fixture de entrada (cópia determinística dos dados de teste)
    fixture = repo_root / "tests" / "fixtures" / "sample_snapshot.csv"
    if not fixture.exists():
        print(f"Fixture não encontrada: {fixture}", file=sys.stderr)
        return 2
    # decidir diretório de saída e validá-lo
    snapshot_dir = choose_snapshot_dir(repo_root)
    try:
        validate_snapshot_dir(snapshot_dir, repo_root)
    except ValueError as exc:
        print(f"Erro: configuração de diretório inválida: {exc}", file=sys.stderr)
        return 6
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    try:
        df = pd.read_csv(fixture)
    except Exception as exc:
        print(f"Falha ao ler fixture {fixture}: {exc}", file=sys.stderr)
        return 3

    # import local para evitar carregar heavy deps cedo
    try:
        from src.etl.snapshot import write_snapshot
    except Exception as exc:
        print(f"Falha ao importar write_snapshot: {exc}", file=sys.stderr)
        return 4

    out_path = snapshot_dir / "PETR4_snapshot.csv"
    try:
        checksum = write_snapshot(df, out_path)
    except Exception as exc:
        print(f"Falha ao escrever snapshot: {exc}", file=sys.stderr)
        return 5

    print(f"Snapshot gerado: {out_path}")
    print(f"Checksum: {checksum}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

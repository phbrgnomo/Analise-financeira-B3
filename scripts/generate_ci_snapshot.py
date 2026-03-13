#!/usr/bin/env python3
"""Gerador CI para criar o snapshot `PETR4_snapshot.csv` em um diretório alvo.

Usa a fixture `tests/fixtures/sample_snapshot.csv` e a função
`src.etl.snapshot.write_snapshot` para escrever o CSV com a
serialização canônica do projeto (determinística).

O destino padrão é `$SNAPSHOT_DIR` se definido, senão `$RUNNER_TEMP/snapshots_test`,
senão `./snapshots_test`.
"""

from __future__ import annotations

import contextlib
import os
import sys
import tempfile
from pathlib import Path
from typing import Sequence, Union

try:
    import pandas as pd
except ImportError:  # pragma: no cover - runtime dependency
    print("Erro: pandas é necessário.", file=sys.stderr)
    raise


def _sanitize_env_value(val: str) -> str:
    """Remove bytes nulos e espaços acidentais de valores de ambiente."""
    if not isinstance(val, str):
        raise ValueError("Valor da variável de ambiente não é uma string")
    return val.split("\x00", 1)[0].strip()


def safe_path_under(
    base: Union[str, Path],
    user_value: str,
    extra_allowed: Sequence[Union[str, Path]] | None = None,
) -> Path:
    """
    Constrói um `Path` a partir de `user_value` e garante que o resultado
    esteja dentro de `base` ou de quaisquer caminhos em `extra_allowed`.

    Lança `ValueError` se o caminho for inválido ou ficar fora das raízes
    permitidas. Esta função centraliza sanitização e validação para reduzir
    superfícies de ataque de path traversal quando lidamos com variáveis
    de ambiente.
    """
    # Resolve a base em modo não-strito para evitar exceções quando o
    # diretório ainda não existir (ex.: diretórios temporários gerados
    # posteriormente).
    base_path = Path(base).resolve(strict=False)
    val = _sanitize_env_value(user_value)

    if not val:
        raise ValueError("Valor de caminho vazio ou inválido")

    candidate = _build_candidate(base_path, val)

    # Construir lista de raízes permitidas (base + extras) via helper
    # Reutilize _build_allowed_roots para manter a construção de raízes
    # consistente com `validate_snapshot_dir`.
    allowed_roots = _build_allowed_roots(base_path, extra_allowed)

    if _is_within_allowed_roots(candidate, allowed_roots):
        return candidate

    raise ValueError("Caminho fora do diretório permitido")


def _build_candidate(base_path: Path, val: str) -> Path:
    """Cria e resolve um `Path` candidato a partir do valor do usuário.

    Resolve com `strict=False` porque a existência do caminho não é um
    requisito para a validação de contenção.
    """
    try:
        candidate = Path(val)
    except TypeError:
        raise ValueError("Valor de caminho inválido") from None

    if not candidate.is_absolute():
        candidate = base_path / candidate

    try:
        return candidate.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise ValueError("Falha ao resolver o caminho do usuário") from exc


def _is_within_allowed_roots(candidate: Path, allowed_roots: Sequence[Path]) -> bool:
    """Retorna True se `candidate` estiver sob qualquer uma das `allowed_roots`.

    Usa `resolve(strict=False)` nas raízes para evitar comportamento diferente
    quando diretórios ainda não existem.
    """
    for root in allowed_roots:
        try:
            root_res = root.resolve(strict=False)
        except (OSError, RuntimeError):
            root_res = root

        try:
            if candidate.is_relative_to(root_res):
                return True
        except AttributeError:
            try:
                if os.path.commonpath([str(root_res), str(candidate)]) == str(root_res):
                    return True
            except ValueError:
                continue

    return False


def _build_allowed_roots(
    repo_root: Path, extra_allowed: Sequence[os.PathLike[str] | str] | None
) -> list[Path]:
    """Retorna uma lista de raízes permitidas (resolvidas com strict=False).

    Inclui `repo_root`, o diretório temporário do sistema e quaisquer
    `extra_allowed` fornecidos, ignorando entradas inválidas.

    Aceita caminhos adicionais como `Path`, `os.PathLike` ou `str`.
    """
    repo_resolved = repo_root.resolve(strict=False)
    system_tmp = Path(tempfile.gettempdir()).resolve(strict=False)

    roots: list[Path] = [repo_resolved, system_tmp]
    if extra_allowed:
        for r in extra_allowed:
            try:
                roots.append(Path(r).resolve(strict=False))
            except (TypeError, OSError, ValueError):
                continue
    return roots


def _choose_from_snapshot_env(repo_root: Path) -> Path | None:
    """Decide um `snapshot_dir` a partir da variável de ambiente `SNAPSHOT_DIR`.

    Inputs:
    - `repo_root`: raiz do repositório usada como referência para caminhos relativos.

    Saída:
    - `Path` resolvido se `SNAPSHOT_DIR` for válido e seguro; caso contrário `None`.

    Segurança:
    - Usa `safe_path_under` para impedir path traversal. Se `safe_path_under`
                rejeitar o valor, esta função NÃO reconstrói `Path(sanitized)` (isso
      evitaria contornar a checagem) e retorna `None` para permitir que o
      fluxo de fallback continue com segurança.
    """
    raw_snapshot_dir = os.environ.get("SNAPSHOT_DIR")
    if raw_snapshot_dir is None:
        return None

    try:
        sanitized = _sanitize_env_value(raw_snapshot_dir)
    except ValueError:
        sanitized = ""

    if not sanitized:
        return None

    # Preparar raízes extras (RUNNER_TEMP se presente)
    extra_roots: list[Path] = []
    if runner_env := os.environ.get("RUNNER_TEMP"):
        with contextlib.suppress(ValueError):
            if runner_sanitized := _sanitize_env_value(runner_env):
                extra_roots.append(Path(runner_sanitized))

    # Conformidade de segurança: não reconstrua um `Path` a partir do valor
    # sanitizado se `safe_path_under` falhar — isso preserva a proteção
    # contra path traversal.
    try:
        candidate = safe_path_under(repo_root, sanitized, extra_allowed=extra_roots)
    except ValueError:
        # Mensagem curta para não exceder o limite de comprimento de linha
        print(
            "Aviso: SNAPSHOT_DIR inválida ou insegura; usando fallback.",
            file=sys.stderr,
        )
        return None

    try:
        validate_snapshot_dir(candidate, repo_root, extra_allowed=extra_roots)
        return candidate.resolve()
    except ValueError as exc:
        print(
            f"Aviso: variável SNAPSHOT_DIR inválida: {exc}; usando fallback.",
            file=sys.stderr,
        )
        return None


def _choose_from_runner_temp(repo_root: Path) -> Path | None:
    """Escolhe `RUNNER_TEMP/snapshots_test` se `RUNNER_TEMP` estiver definido.

    Segurança: valida `raw_runner` via `_sanitize_env_value` e `safe_path_under`
        para garantir que a base é segura; retorna `None` em caso de erro.
    """
    raw_runner_env = os.environ.get("RUNNER_TEMP")
    if raw_runner_env is None:
        return None

    try:
        raw_runner = _sanitize_env_value(raw_runner_env)
    except ValueError:
        raw_runner = ""

    if not raw_runner:
        return None

    try:
        runner_base = safe_path_under(tempfile.gettempdir(), raw_runner)
    except ValueError:
        return None

    candidate = runner_base / "snapshots_test"
    try:
        validate_snapshot_dir(candidate, repo_root, extra_allowed=[runner_base])
        return candidate.resolve()
    except ValueError as exc:
        msg = (
            "Aviso: RUNNER_TEMP inválido ou fora dos diretórios permitidos: "
            f"{exc}; usando fallback."
        )
        print(msg, file=sys.stderr)
        return None


def choose_snapshot_dir(repo_root: Path) -> Path:
    """Decide e retorna o `snapshot_dir` preferido com validação básica.

    Prioridade: `SNAPSHOT_DIR` > `RUNNER_TEMP/snapshots_test` > repo_root/snapshots_test
    """
    if snap := _choose_from_snapshot_env(repo_root):
        return snap

    if snap := _choose_from_runner_temp(repo_root):
        return snap

    return repo_root / "snapshots_test"


def validate_snapshot_dir(
    snapshot_dir: Path,
    repo_root: Path,
    extra_allowed: Sequence[Path] | None = None,
) -> None:
    """Valida que `snapshot_dir` está dentro de `repo_root`, do temp do sistema,
    ou de quaisquer raízes adicionais fornecidas em `extra_allowed`.

    Lança `ValueError` se inválido.
    """
    # Use resolve não-strito porque a existência não é necessária para
    # validação de contenção (útil para diretórios temporários de CI que
    # podem ser criados posteriormente).
    resolved_snapshot = snapshot_dir.resolve(strict=False)

    roots = _build_allowed_roots(repo_root, extra_allowed)

    if _is_within_allowed_roots(resolved_snapshot, roots):
        return

    raise ValueError("Diretório de snapshot fora dos diretórios permitidos")


def _compute_and_persist_metadata(out_path: Path, df) -> str:
    """Compute checksum/size/rows and persist metadata to DB for CI.

    Returns the checksum string on success or empty string on failure.
    """
    try:
        from src import db
        from src.utils.checksums import sha256_file  # local import
    except Exception as exc:  # pragma: no cover - defensive
        print(f"Falha ao importar helpers de checksum/DB: {exc}", file=sys.stderr)
        return ""

    try:
        checksum = sha256_file(out_path)
        size = out_path.stat().st_size
        rows = len(df)
        metadata = {
            "ticker": "PETR4",
            "created_at": None,
            "snapshot_path": str(out_path.resolve()),
            "rows": rows,
            "checksum": checksum,
            "size_bytes": size,
        }
        try:
            if db_path_override := os.environ.get("SNAPSHOT_DB"):
                conn = db.connect(db_path=db_path_override)
                try:
                    db.record_snapshot_metadata(metadata, conn=conn)
                finally:
                    conn.close()
            else:
                db.record_snapshot_metadata(metadata)
        except Exception as rec_exc:
            print(f"Aviso: falha ao gravar metadata no DB: {rec_exc}", file=sys.stderr)
        return checksum
    except Exception as exc:
        print(f"Falha ao computar checksum/metadata: {exc}", file=sys.stderr)
        return ""


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]

    # localizar fixture de entrada (cópia determinística dos dados de teste)
    fixture = repo_root / "tests" / "fixtures" / "sample_snapshot.csv"
    if not fixture.exists():
        print(f"Fixture não encontrada: {fixture}", file=sys.stderr)
        return 2
    # decidir diretório de saída e validá-lo
    snapshot_dir = choose_snapshot_dir(repo_root)
    # Construir raízes adicionais permitidas (ex.: RUNNER_TEMP) para a
    # validação final. `choose_snapshot_dir` já valida internamente com
    # extras, mas ao revalidar aqui devemos manter a mesma tolerância a
    # diretórios temporários do runner para evitar rejeições redundantes.
    extra_allowed: list[Path] = []
    if runner_env := os.environ.get("RUNNER_TEMP"):
        with contextlib.suppress(ValueError):
            if runner_sanitized := _sanitize_env_value(runner_env):
                extra_allowed.append(Path(runner_sanitized))
    try:
        validate_snapshot_dir(snapshot_dir, repo_root, extra_allowed=extra_allowed)
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
        print(f"Falha ao importar write_snapshot ou helpers: {exc}", file=sys.stderr)
        return 4

    out_path = snapshot_dir / "PETR4_snapshot.csv"
    try:
        _ = write_snapshot(df, out_path)
    except Exception as exc:
        print(f"Falha ao escrever snapshot: {exc}", file=sys.stderr)
        return 5

    # compute authoritative checksum and persist metadata for CI consumers
    checksum = _compute_and_persist_metadata(out_path, df)
    if not checksum:
        return 6

    print(f"Snapshot gerado: {out_path}")
    print(f"Checksum: {checksum}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

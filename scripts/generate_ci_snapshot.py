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
from typing import Sequence, Union

try:
    import pandas as pd
except Exception:  # pragma: no cover - runtime dependency
    print("Erro: pandas é necessário.", file=sys.stderr)
    raise


def _sanitize_env_value(val: str) -> str:
    """Remove bytes nulos e espaços acidentais de valores de ambiente."""
    if not isinstance(val, str):
        raise ValueError("Valor da variável de ambiente não é uma string")
    return val.split("\x00", 1)[0].strip()


def _resolve_allowed_roots(
    base: Union[str, Path], extra_allowed: Sequence[Union[str, Path]] | None
):
    """Resolve and return a list of Path roots from base and extra_allowed.

    This helper keeps `safe_path_under` smaller to satisfy complexity
    linters while centralizing resolution logic.
    """
    # Sanitize and resolve base (base may come from env in some callers)
    if isinstance(base, str):
        base_val = _sanitize_env_value(base)
    else:
        base_val = str(base)

    roots: list[Path] = []
    try:
        roots.append(Path(base_val).resolve())
    except Exception:
        # If base cannot be resolved, fallback empty list (caller will handle)
        pass

    if extra_allowed:
        for r in extra_allowed:
            try:
                if isinstance(r, str):
                    r_val = _sanitize_env_value(r)
                else:
                    r_val = str(r)
                roots.append(Path(r_val).resolve())
            except Exception:
                # ignore invalid extras
                continue
    return roots


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
    base_path = Path(base).resolve()
    val = _sanitize_env_value(user_value)

    if not val:
        raise ValueError("Valor de caminho vazio ou inválido")

    try:
        candidate = Path(val)
    except Exception:
        raise ValueError("Valor de caminho inválido") from None

    if not candidate.is_absolute():
        candidate = base_path / candidate

    try:
        candidate = candidate.resolve(strict=False)
    except Exception as exc:
        raise ValueError("Falha ao resolver o caminho do usuário") from exc

    # Construir lista de raízes permitidas (base + extras) via helper
    allowed_roots = _resolve_allowed_roots(base_path, extra_allowed)

    for root in allowed_roots:
        try:
            if candidate.is_relative_to(root):
                return candidate
        except AttributeError:
            if os.path.commonpath([str(root), str(candidate)]) == str(root):
                return candidate

    raise ValueError("Caminho fora do diretório permitido")


def choose_snapshot_dir(repo_root: Path) -> Path:  # noqa: C901
    """Decide e retorna o `snapshot_dir` preferido com validação básica.

    Prioridade: `SNAPSHOT_DIR` > `RUNNER_TEMP/snapshots_test` > repo_root/snapshots_test
    """
    snapshot_dir = None

    raw_snapshot_dir = os.environ.get("SNAPSHOT_DIR")
    if raw_snapshot_dir is not None:
        # Sanitizar e tratar valores vazios/whitespace como não definidos
        try:
            sanitized = _sanitize_env_value(raw_snapshot_dir)
        except ValueError:
            sanitized = ""

        if sanitized:
            # Construir candidate e validar contra repo_root, system tmp e
            # RUNNER_TEMP (se presente).
            # Preparar raízes extras antes de tentar resolver o candidate via
            # `safe_path_under` para evitar usar variável indefinida.
            extra_roots: list[Path] = []
            runner_env = os.environ.get("RUNNER_TEMP")
            if runner_env:
                try:
                    runner_sanitized = _sanitize_env_value(runner_env)
                    if runner_sanitized:
                        # normalize and keep as Path for type consistency; resolution
                        # will happen later in safe_path_under or validate functions
                        extra_roots.append(Path(runner_sanitized))
                except ValueError:
                    pass

            # Construir candidate de forma segura considerando raízes adicionais
            # (ex.: RUNNER_TEMP) — a validação final é feita por
            # `validate_snapshot_dir`, mas aqui usamos `safe_path_under` para
            # reduzir superfícies de criação de `Path` inseguras.
            try:
                candidate = safe_path_under(
                    repo_root, sanitized, extra_allowed=extra_roots
                )
            except ValueError:
                # fallback para comportamento legado: construir Path e deixar
                # validate_snapshot_dir emitir erro mais detalhado
                candidate = Path(sanitized)

            try:
                validate_snapshot_dir(candidate, repo_root, extra_allowed=extra_roots)
                snapshot_dir = candidate.resolve()
            except ValueError as exc:
                msg = (
                    "Aviso: variável SNAPSHOT_DIR inválida: "
                    f"{exc}; usando fallback."
                )
                print(msg, file=sys.stderr)

    if snapshot_dir is None and os.environ.get("RUNNER_TEMP"):
        try:
            raw_runner = _sanitize_env_value(os.environ["RUNNER_TEMP"])
            # Garantir que RUNNER_TEMP esteja dentro do tmp do sistema ou
            # de raízes permitidas; safe_path_under valida e resolve o caminho.
            try:
                runner_base = safe_path_under(tempfile.gettempdir(), raw_runner)
            except ValueError:
                raise

            candidate = runner_base / "snapshots_test"
            try:
                validate_snapshot_dir(candidate, repo_root, extra_allowed=[runner_base])
                snapshot_dir = candidate.resolve()
            except ValueError as exc:
                msg = (
                    "Aviso: RUNNER_TEMP inválido ou fora dos diretórios permitidos: "
                    f"{exc}; usando fallback."
                )
                print(msg, file=sys.stderr)
        except Exception:
            print("Aviso: RUNNER_TEMP inválido; usando fallback.", file=sys.stderr)

    if snapshot_dir is None:
        snapshot_dir = repo_root / "snapshots_test"

    return snapshot_dir


def validate_snapshot_dir(
    snapshot_dir: Path,
    repo_root: Path,
    extra_allowed: Sequence[Path] | None = None,
) -> None:
    """Valida que `snapshot_dir` está dentro de `repo_root`, do temp do sistema,
    ou de quaisquer raízes adicionais fornecidas em `extra_allowed`.

    Lança `ValueError` se inválido.
    """
    resolved_snapshot = snapshot_dir.resolve()
    allowed = False
    repo_resolved = repo_root.resolve()
    system_tmp = Path(tempfile.gettempdir()).resolve()

    roots: list[Path] = [repo_resolved, system_tmp]
    if extra_allowed:
        for r in extra_allowed:
            try:
                roots.append(Path(r).resolve())
            except Exception:
                # ignore invalid extra roots
                continue

    for root in roots:
        try:
            if resolved_snapshot.is_relative_to(root):
                allowed = True
                break
        except AttributeError:
            import os as _os

            try:
                common = _os.path.commonpath([str(root), str(resolved_snapshot)])
                if common == str(root):
                    allowed = True
                    break
            except Exception:
                continue

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

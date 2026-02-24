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
except Exception:  # pragma: no cover - runtime dependency
    print("Erro: pandas é necessário.", file=sys.stderr)
    raise


def _sanitize_env_value(val: str) -> str:
    """Remove bytes nulos e espaços acidentais de valores de ambiente."""
    if not isinstance(val, str):
        raise ValueError("Valor da variável de ambiente não é uma string")
    return val.split("\x00", 1)[0].strip()


def _resolve_allowed_roots(
    base: Path, extra_allowed: Sequence[Union[str, Path]] | None
) -> list[Path]:
    """Resolve e retorna raízes `Path` a partir de `base` e `extra_allowed`.

    `base` espera-se que já seja um `Path` sanitizado e resolvido fornecido
    pelo chamador. Este helper centraliza a lógica de resolução para raízes
    adicionais permitidas (que ainda podem ser strings originadas do
    ambiente).
    """
    roots: list[Path] = [base]
    if extra_allowed:
        for r in extra_allowed:
            try:
                r_val = _sanitize_env_value(r) if isinstance(r, str) else str(r)
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

    Security: valida `raw_runner` via `_sanitize_env_value` e `safe_path_under`
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

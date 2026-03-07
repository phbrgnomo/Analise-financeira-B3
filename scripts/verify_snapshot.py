#!/usr/bin/env python3
"""Wrapper CLI to validate snapshots using scripts/validate_snapshots.py.

This small script forwards args to the existing validation script and returns
its exit code. It simplifies CI step commands and makes intent explicit.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """
    Executa o validador de snapshots em `scripts/validate_snapshots.py`.

    Parâmetros:
    - argv: lista de argumentos (por padrão usa `sys.argv[1:]`).

    Retorno:
    - Código de saída retornado pelo script de validação (inteiro).

    Observações:
    - Este wrapper encaminha os argumentos para o script de validação
      e retorna seu código de saída. Preserva o tratamento de
      KeyboardInterrupt e captura erros de execução.
    """
    if argv is None:
        argv = sys.argv[1:]

    # Definir `repo_root` como a raiz do projeto (um nível acima do pacote
    # scripts/). Isso garante que checagens de fallback para
    # `scripts/validate_snapshots.py` funcionem corretamente.
    repo_root = Path(__file__).resolve().parents[1]
    validate = repo_root / "scripts" / "validate_snapshots.py"
    # Fallback: caso o script esteja no diretório do repositório em vez de
    # scripts/, tente `repo_root / 'validate_snapshots.py'`.
    if not validate.exists():
        validate = repo_root / "validate_snapshots.py"

    if not validate.exists():
        print("Erro: scripts/validate_snapshots.py não encontrado", file=sys.stderr)
        return 2

    comando = [sys.executable, str(validate)] + list(argv)

    # sanity-check all components are simple strings; this is defensive and
    # documents the assumption that user args do not inject shell metachars.
    # ``subprocess.run`` is invoked with ``shell=False`` and a sequence, which
    # already prevents shell interpretation, but static analyzers sometimes
    # flag the pattern unless we emphasise that ``argv`` elements are safe.
    for part in comando:
        if not isinstance(part, str):
            raise TypeError(f"invalid command component: {part!r}")
        # forbid line breaks which could confuse some wrappers
        if "\n" in part or "\r" in part:
            raise ValueError(f"unsafe argument containing newline: {part!r}")

    try:
        # Use subprocess.run com lista de argumentos e shell=False para evitar
        # interpretação pelo shell de entrada do usuário (mitiga CWE-78).
        # The *argv* list comes directly from our own CLI parsing and is never
        # concatenated into a string, so there is no opportunity for shell
        # injection.  We also avoid passing user input to `env` or similar.
        retorno_proc = subprocess.run(comando, shell=False)
        return retorno_proc.returncode
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"Erro ao executar validação: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

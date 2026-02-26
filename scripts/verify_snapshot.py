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
    try:
        # Use subprocess.run com lista de argumentos e shell=False para evitar
        # interpretação pelo shell de entrada do usuário (mitiga CWE-78).
        retorno_proc = subprocess.run(comando, shell=False)
        return retorno_proc.returncode
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"Erro ao executar validação: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

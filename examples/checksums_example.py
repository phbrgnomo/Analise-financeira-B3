"""Exemplo de uso para src.utils.checksums.sha256_file e sha256_bytes.

Este script calcula o checksum SHA256 de um arquivo de exemplo e grava um
arquivo `.checksum` ao lado do arquivo original.

Uso:
    python examples/checksums_example.py
"""

from pathlib import Path

from src.utils.checksums import sha256_file


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sample = repo_root / "snapshots" / "PETR4_snapshot_test.csv"
    if not sample.exists():
        print(f"Arquivo de exemplo não encontrado: {sample}")
        return

    checksum = sha256_file(sample)
    checksum_file = sample.with_suffix(sample.suffix + ".checksum")
    checksum_file.write_text(checksum)

    print(f"Arquivo: {sample}")
    print(f"SHA256: {checksum}")
    print(f"Escrito: {checksum_file}")


if __name__ == "__main__":
    main()

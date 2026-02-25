import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from src.utils.checksums import serialize_df_bytes, sha256_bytes


def _write_csv(path: Path) -> None:
    """Write a small CSV and its SHA-256 checksum to disk.

    Creates parent directories as needed, writes deterministic CSV bytes to
    `path` and writes a companion `.checksum` file containing the SHA-256
    hex digest.

    Args:
        path (Path): target file path for the CSV.

    Returns:
        None
    """

    data = serialize_df_bytes(
        pd.DataFrame({"Date": ["2020-01-01"], "Close": [10.0]}),
        index=False,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.with_suffix(path.suffix + ".checksum").write_text(sha256_bytes(data))


def test_update_writes_manifest(tmp_path: Path):
    """Gera um manifesto a partir de um diretório e verifica que o arquivo é escrito.

    Cenário: invoca `scripts/validate_snapshots.py --update --allow-external`
    em um diretório temporário contendo um CSV de amostra e verifica que
    o manifesto gerado contém a chave `files` com um mapping.
    """
    cur_dir = tmp_path / "cur"
    cur_dir.mkdir()
    f = cur_dir / "SAMPLE.csv"
    _write_csv(f)

    manifest = tmp_path / "out_manifest.json"

    script = Path(__file__).resolve().parent.parent / "scripts" / "validate_snapshots.py"
    cmd = [
        sys.executable,
        str(script),
        "--dir",
        str(cur_dir),
        "--manifest",
        str(manifest),
        "--update",
        "--allow-external",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, (
        f"Falha na geração do manifesto: {proc.stderr}\n{proc.stdout}"
    )
    assert manifest.exists()
    data = json.loads(manifest.read_text())
    assert "files" in data
    assert isinstance(data["files"], dict)


def test_allow_external_remap_collision(tmp_path: Path):
    """Verifica que colisões de basename com `--allow-external` causam erro.

    Cria dois arquivos com o mesmo basename em subdiretórios diferentes e
    espera que o comando falhe com código 3 indicando colisão.
    """
    # cria dois arquivos com mesmo basename em subdirs diferentes
    d = tmp_path / "d"
    p1 = d / "a" / "same.csv"
    p2 = d / "b" / "same.csv"
    _write_csv(p1)
    _write_csv(p2)

    manifest = tmp_path / "m.json"

    script = Path(__file__).resolve().parent.parent / "scripts" / "validate_snapshots.py"
    cmd = [
        sys.executable,
        str(script),
        "--dir",
        str(d),
        "--manifest",
        str(manifest),
        "--allow-external",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    # colisão deve provocar código de saída 3 (SystemExit(3))
    assert proc.returncode == 3


def test_invalid_manifest_path_errors(tmp_path: Path):
    """Chama o validador com um manifesto fora de `snapshots/` e espera falha.

    Sem `--allow-external` a execução deve retornar código 2.
    """
    # chamar com manifesto fora de snapshots/ sem --allow-external deve falhar
    d = tmp_path / "d"
    d.mkdir()
    p = d / "ok.csv"
    _write_csv(p)

    manifest = tmp_path / "out" / "m.json"

    script = Path(__file__).resolve().parent.parent / "scripts" / "validate_snapshots.py"
    cmd = [
        sys.executable,
        str(script),
        "--dir",
        str(d),
        "--manifest",
        str(manifest),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 2

import subprocess
import sys
from pathlib import Path

import pandas as pd

from src.utils.checksums import serialize_df_bytes, sha256_bytes


def _make_csv_bytes() -> bytes:
    """Cria um DataFrame pequeno determinístico e retorna bytes CSV.

    O CSV é serializado de forma determinística para uso em testes E2E.
    """
    # dataframe pequeno determinístico
    df = pd.DataFrame({"Date": ["2020-01-01", "2020-01-02"], "Close": [10.0, 11.5]})
    return serialize_df_bytes(
        df,
        index=False,
        date_format="%Y-%m-%dT%H:%M:%S",
        float_format="%.10g",
    )


def test_acceptance_snapshot(tmp_path: Path):
    """Verifica o fluxo de validação de snapshots.

    O teste cria um diretório determinístico de snapshots, escreve um arquivo
    de snapshot e seu checksum, gera um manifesto para esse diretório
    (usando a opção --update) e executa a validação via wrapper. O teste
    assegura que a geração do manifesto e a validação retornem sucesso.
    """

    # Cria um diretório de snapshots determinístico com arquivos que serão remapeados
    out = tmp_path / "snapshots_test"
    out.mkdir()

    # Cria um único arquivo de snapshot com o mesmo basename do manifesto do repositório
    name = "PETR4_snapshot.csv"
    fp = out / name
    data = _make_csv_bytes()
    fp.write_bytes(data)

    # grava arquivo de checksum no mesmo formato que o pipeline usa
    chk = fp.with_suffix(fp.suffix + ".checksum")
    chk.write_text(sha256_bytes(data))

    # Primeiro gera um manifesto para este diretório temporário,
    # depois valida contra ele
    tmp_manifest = tmp_path / "manifest.json"
    gen_cmd = [
        sys.executable,
        "scripts/validate_snapshots.py",
        "--dir",
        str(out),
        "--manifest",
        str(tmp_manifest),
        "--update",
        "--allow-external",
    ]
    gen = subprocess.run(gen_cmd, capture_output=True, text=True, timeout=60)
    assert gen.returncode == 0, (
        f"Manifest generation failed: {gen.stderr}\n{gen.stdout}"
    )

    # Chama o wrapper que encaminha para scripts/validate_snapshots.py
    # Monta o caminho do script relativo a este arquivo de teste
    # para não depender do CWD
    verify = (
        Path(__file__).resolve().parent.parent.parent
        / "scripts"
        / "verify_snapshot.py"
    )
    validate_cmd = [
        sys.executable,
        str(verify),
        "--dir",
        str(out),
        "--manifest",
        str(tmp_manifest),
        "--allow-external",
    ]
    proc = subprocess.run(validate_cmd, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, (
        "Snapshot validation failed:\n"
        f"STDOUT: {proc.stdout}\n"
        f"STDERR: {proc.stderr}"
    )

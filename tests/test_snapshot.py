import logging
from pathlib import Path

from src.etl import snapshot as snapshot_module

# module-level helper counter to ensure deterministic mtimes when no
# explicit timestamp is provided.
_make_file_counter = 0

def _make_file(path: Path, mtime: float | None = None):
    """Create an empty file and set its modification time.

    The helper is used by snapshot tests to produce files with predictable
    mtimes so pruning logic can rely on chronological ordering.  If
    ``mtime`` is provided (a POSIX timestamp), it will be applied; otherwise
    an internal counter is used to guarantee each call gets a distinct time.

    Args:
        path: target path for the new file
        mtime: optional timestamp to assign as both access and modification
            time.  When omitted, an incrementing counter ensures determinism.
    """
    path.write_text("")
    if mtime is None:
        # use module-level counter instead of function attribute
        global _make_file_counter
        _make_file_counter += 1
        mtime = _make_file_counter
    import os

    os.utime(path, (mtime, mtime))
    return path


def test_prune_old_snapshots_deletes_and_logs(tmp_path, caplog, monkeypatch):
    """Verifica remoção de snapshots antigos e log da operação.

    Cria três arquivos nomeados sequencialmente e força a política de manter
    apenas o mais novo.  Após executar ``_prune_old_snapshots`` usando o
    caminho do último arquivo, apenas este deve permanecer no diretório e um
    registro de debug deve mencionar que os arquivos antigos foram removidos.
    """
    # manter apenas o arquivo mais recente
    monkeypatch.setattr(snapshot_module, "_snapshot_keep_latest", lambda: 1)
    # criar três snapshots com timestamps crescentes
    p1 = _make_file(tmp_path / "PETR4-20220101T000000.csv")
    p2 = _make_file(tmp_path / "PETR4-20220102T000000.csv")
    p3 = _make_file(tmp_path / "PETR4-20220103T000000.csv")

    caplog.set_level(logging.DEBUG)
    # chamar a função de prune utilizando o caminho do arquivo mais novo
    snapshot_module._prune_old_snapshots(p3)

    # apenas o mais recente deve permanecer
    assert not p1.exists(), "snapshot mais antigo deve ser removido"
    assert not p2.exists(), "snapshot intermediário deve ser removido"
    assert p3.exists(), "snapshot mais recente deve ser mantido"

    # o log deve mencionar a remoção de snapshots antigas
    assert "removendo snapshot antiga" in caplog.text


def test_prune_old_snapshots_pattern_mismatch_logs(tmp_path, caplog):
    """Arquivo com nome que não corresponde ao padrão deve emitir um WARNING
    e ser ignorado."""
    caplog.set_level(logging.WARNING)
    fake = tmp_path / "not-a-snapshot.csv"
    fake.write_text("")
    snapshot_module._prune_old_snapshots(fake)
    assert "não combina com padrão" in caplog.text
    # só nos interessa que o aviso foi emitido; detalhes de debug são opcionais.

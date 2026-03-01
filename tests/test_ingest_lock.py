import json
import os
import subprocess
import sys
import time

import pytest

from src import locks


def test_acquire_lock_basic(tmp_path) -> None:
    """Verificações básicas de sanidade no gerenciador de contexto de bloqueio."""
    os.environ["LOCK_DIR"] = str(tmp_path)
    # obtém um bloqueio e mantém manualmente
    ctx = locks.acquire_lock("T", timeout_seconds=1, wait=True)
    lock_meta = ctx.__enter__()
    assert lock_meta["lock_action"] == "acquired"

    # segunda tentativa não bloqueante deve falhar imediatamente
    with pytest.raises(locks.LockTimeout):
        with locks.acquire_lock("T", timeout_seconds=0, wait=False):
            pass

    ctx.__exit__(None, None, None)


def test_acquire_lock_timeout(tmp_path) -> None:
    """Uma tentativa bloqueante deve respeitar o tempo limite sem ser
    excessivamente rigorosa com o tempo de relógio."""
    os.environ["LOCK_DIR"] = str(tmp_path)
    # mantém o bloqueio
    ctx = locks.acquire_lock("X", timeout_seconds=1, wait=True)
    ctx.__enter__()

    timeout = 0.1
    start = time.monotonic()
    with pytest.raises(locks.LockTimeout) as excinfo:
        with locks.acquire_lock(
            "X",
            timeout_seconds=timeout,
            wait=True,
        ) as blocking_ctx:
            pass  # pragma: no cover - não deve chegar aqui
    waited = time.monotonic() - start

    assert waited >= timeout * 0.8

    # se a exceção carrega metadados do contexto podemos verificar também
    lock_timeout_exc = excinfo.value
    blocking_ctx = getattr(lock_timeout_exc, "lock_ctx", None)
    if blocking_ctx is not None and hasattr(blocking_ctx, "lock_waited_seconds"):
        assert blocking_ctx.lock_waited_seconds >= timeout
        assert blocking_ctx.lock_waited_seconds <= waited * 1.2

    ctx.__exit__(None, None, None)


def run_ingest_process(tmp_path, env_vars):
    """Inicia um processo Python separado que executa o helper de ingestão.

    Evitamos chamar o CLI do Typer diretamente porque a combinação atual do
    Typer + Python 3.14 apresenta bugs de parsing (``--source`` é tratado
    como flag).  Em vez disso executamos um pequeno snippet ``-c`` que
    importa :func:`ingest_command` e sai com seu código de retorno.  Isso
    mantém o teste focado em bloqueios, não em peculiaridades do CLI.
    """
    # monta um pequeno programa que chama ingest_command com o provedor dummy
    # e ticker "TICK"; variáveis de ambiente controlarão o comportamento de
    # bloqueio.
    py = (
        "import sys;"
        "from src.ingest.pipeline import ingest_command;"
        "sys.exit(ingest_command('TICK','dummy', dry_run=True))"
    )
    cmd = [sys.executable, "-c", py]
    env = os.environ.copy()
    env.update(env_vars)
    return subprocess.Popen(
        cmd,
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_concurrent_waiting(tmp_path) -> None:
    """Quando o modo padrão "wait" está ativo, a segunda ingestão deve
    bloquear até que a primeira libere o bloqueio e então ter sucesso.
    """
    env = {
        "LOCK_DIR": str(tmp_path / "locks"),
        "INGEST_LOCK_TIMEOUT_SECONDS": "2",
        "DUMMY_SLEEP": "1",
    }
    p1 = run_ingest_process(tmp_path, env)
    # aguarda até que o processo p1 realmente tenha criado o arquivo de
    # bloqueio no diretório configurado.  Isso evita flakiness em ambientes
    # lentos em que um sleep fixo não é suficiente.
    lock_file = tmp_path / "locks" / "TICK.lock"
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if lock_file.exists():
            break
        time.sleep(0.05)
    else:
        pytest.fail("p1 não criou arquivo de bloqueio dentro do tempo esperado")

    env2 = env.copy()
    env2.pop("DUMMY_SLEEP", None)
    p2 = run_ingest_process(tmp_path, env2)

    out1, err1 = p1.communicate(timeout=10)
    out2, err2 = p2.communicate(timeout=10)

    assert p1.returncode == 0
    assert p2.returncode == 0

    # o log de metadados deve conter informação de bloqueio para ambas as
    # execuções
    log_path = tmp_path / "metadata" / "ingest_logs.jsonl"
    assert log_path.exists(), (
        "esperava que o log de metadados fosse criado"
    )
    with open(log_path, "r") as f:
        lines = [json.loads(line) for line in f]
    assert all(
        "started_at" in entry and "finished_at" in entry
        for entry in lines
    ), "timestamps ausentes"
    assert any(entry.get("lock_action") == "acquired" for entry in lines)
    # pelo menos uma das entradas deve mostrar tempo de espera não zerado
    assert any(entry.get("lock_waited_seconds", 0) > 0 for entry in lines)


def test_lock_released_on_exception(tmp_path) -> None:
    """O gerenciador de contexto deve liberar o bloqueio mesmo se uma
    exceção for levantada.

    Adquire um bloqueio, levanta uma exceção dentro do contexto e então
    garante que podemos obtê-lo novamente imediatamente depois.  Isso evita
    vazamento de recursos.
    """
    os.environ["LOCK_DIR"] = str(tmp_path)
    # primeira aquisição que lança
    with pytest.raises(RuntimeError):
        with locks.acquire_lock("Z", timeout_seconds=1, wait=True):
            raise RuntimeError("boom")
    # após a exceção, uma nova aquisição deve ter sucesso sem timeout
    with locks.acquire_lock("Z", timeout_seconds=0.1, wait=True):
        pass



@pytest.mark.skipif(sys.platform.startswith("win"),
                    reason="fcntl não disponível no Windows")
def test_portalocker_missing_fallback(tmp_path, monkeypatch) -> None:
    """Se a dependência opcional ``portalocker`` estiver ausente, o caminho
    de fallback POSIX ainda deve funcionar corretamente.

    O teste é ignorado no Windows porque o fallback usa ``fcntl`` que não está
    disponível lá.
    """
    os.environ["LOCK_DIR"] = str(tmp_path)
    # simula ambiente sem portalocker
    monkeypatch.setattr(locks, "portalocker", None)
    with locks.acquire_lock("Z", timeout_seconds=0.5, wait=True) as meta:
        assert meta["lock_action"] == "acquired"


def test_concurrent_exit(tmp_path) -> None:
    """Quando o modo é 'exit' o segundo processo deve falhar imediatamente."""
    env = {
        "LOCK_DIR": str(tmp_path / "locks"),
        "INGEST_LOCK_MODE": "exit",
        "DUMMY_SLEEP": "2",
    }
    p1 = run_ingest_process(tmp_path, env)
    time.sleep(0.1)

    env2 = env.copy()
    env2.pop("DUMMY_SLEEP", None)
    p2 = run_ingest_process(tmp_path, env2)

    out1, err1 = p1.communicate(timeout=10)
    out2, err2 = p2.communicate(timeout=10)

    assert p1.returncode == 0
    assert p2.returncode != 0
    assert "lock" in err2.lower()

    # o log de metadados deve registrar a tentativa falha com ação 'exit' e
    # sem espera
    log_path = tmp_path / "metadata" / "ingest_logs.jsonl"
    assert log_path.exists()
    # lê o log uma vez e reutiliza para várias asserções
    with open(log_path, "r") as f:
        raw_lines = f.readlines()
    entries = [json.loads(line) for line in raw_lines]
    exit_entries = [e for e in entries if e.get("lock_action") == "exit"]
    assert exit_entries, "esperava pelo menos uma entrada com lock_action 'exit'"
    assert all(e.get("lock_waited_seconds", 0) == 0 for e in exit_entries)
    # failing run should still log metadata with timestamps
    assert all("started_at" in e and "finished_at" in e for e in entries)

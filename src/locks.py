"""Utilitário simples de bloqueio de arquivo multiplataforma para ingestão por ticker.

Este módulo é usado pelo pipeline de ingestão para garantir que apenas um
processo do mesmo ticker execute a parte de download/ETL/cache/cache/write
(see :mod:`src.ingest.snapshot_ingest` for o fluxo completo).  O bloqueio é
adquirido antes da avaliação de cache e liberado imediatamente após a fase
crítica de escrita, permitindo que o restante do pipeline (e.g. cálculo de
retornos) prossiga em paralelo.

Este módulo fornece um gerenciador de contexto mínimo que serializa o acesso a
um arquivo chamado ``{LOCK_DIR}/{ticker}.lock``. A implementação dá preferência
à biblioteca ``portalocker`` (agora dependência direta do projeto), mas mantém
um fallback POSIX ``fcntl`` como rede de segurança e para facilitar testes do
caminho sem ``portalocker``.

A superfície da API é propositalmente enxuta para que consumidores possam
simplesmente escrever ``with acquire_lock(...) as meta:`` e não se preocupar com
detalhes internos. Toda configuração é dirigida por variáveis de ambiente,
assim o código do pipeline permanece simples e fácil de controlar a partir dos
testes.

Classes
-------
LockTimeout
    Exceção lançada quando uma solicitação de bloqueio não pode ser
    satisfeita no modo solicitado.

Functions
---------
acquire_lock(ticker, timeout_seconds=120, wait=True) -> contextmanager
    Gerenciador de contexto que obtém um bloqueio exclusivo em
    ``{LOCK_DIR}/{ticker}.lock`` e o libera automaticamente ao sair.

"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator

from src.tickers import normalize_b3_ticker

logger = logging.getLogger(__name__)

try:
    import portalocker
except ImportError:  # pragma: no cover - tests will install portalocker
    portalocker = None


# diretório padrão onde os arquivos de bloqueio são armazenados;
# pode ser substituído via LOCK_DIR
# mantém um objeto Path como padrão, mas resolve-o em tempo de execução a
# partir da variável de ambiente.
DEFAULT_LOCK_DIR = Path("locks")


class LockTimeout(Exception):
    """Lançada quando uma requisição de bloqueio não pode ser satisfeita sob o
    tempo limite/comportamento configurado.
    """


def _resolve_lock_dir(env_val: str | None) -> Path:
    """Retorna um Path resolvido para o diretório de bloqueios.

    Expande ~ e converte para um caminho absoluto.
    """
    val = env_val if env_val is not None else str(DEFAULT_LOCK_DIR)
    return Path(val).expanduser().resolve()


def _acquire_with_portalocker(
    fh, flags, wait: bool, timeout_seconds: float, start: float, ticker: str
) -> None:
    """Adquire bloqueio usando portalocker ou lança LockTimeout em caso de falha.

    ``portalocker.lock`` não aceita um argumento ``timeout`` nas versões mais
    recentes, então replicamos a lógica de espera manualmente aqui.  O
    comportamento tenta adquirir o bloqueio em loop até o tempo expirar.
    """
    # the caller only invokes this when ``portalocker`` is available, but
    # type checkers can't prove that, so guard explicitly.
    if portalocker is None:
        raise RuntimeError(
            "_acquire_with_portalocker called but portalocker is not installed"
        )

    # Always attempt non-blocking acquisitions so we can implement our own
    # timeout rather than relying on portalocker's blocking behaviour which
    # would hang indefinitely and freeze the tests.
    flags |= portalocker.LockFlags.NON_BLOCKING

    if not wait:
        try:
            portalocker.lock(fh, flags)
            return
        except portalocker.exceptions.LockException as exc:
            raise LockTimeout(
                f"bloqueio para {ticker} ocupado por outro processo (não bloqueante)"
            ) from exc

    # blocking with timeout: poll in a loop similar to the fcntl path
    end = start + timeout_seconds
    while True:
        try:
            portalocker.lock(fh, flags)
            return
        except portalocker.exceptions.LockException as exc:
            if time.monotonic() >= end:
                waited = time.monotonic() - start
                raise LockTimeout(
                    f"falha ao obter bloqueio para {ticker} após {waited:.3f}s"
                ) from exc
            time.sleep(0.05)


def _acquire_with_fcntl(
    fh, wait: bool, timeout_seconds: float, start: float, ticker: str
) -> None:
    """Adquire bloqueio usando fcntl POSIX com polling de tempo limite opcional."""
    import fcntl

    if not wait:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError as exc:
            raise LockTimeout(
                f"bloqueio para {ticker} ocupado por outro processo (não bloqueante)"
            ) from exc

    end = start + timeout_seconds
    while True:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError as exc:
            if time.monotonic() >= end:
                waited = time.monotonic() - start
                raise LockTimeout(
                    f"falha ao obter bloqueio para {ticker} após {waited:.3f}s"
                ) from exc
            time.sleep(0.05)


@contextmanager
def acquire_lock(
    ticker: str, timeout_seconds: float = 120.0, wait: bool = True
) -> Iterator[Dict[str, Any]]:
    """Adquire um bloqueio de sistema de arquivos para um determinado ticker.

    Parameters
    ----------
    ticker : str
        O nome do ticker; o arquivo de bloqueio será ``{LOCK_DIR}/{ticker}.lock``.
    timeout_seconds : int
        Tempo máximo para aguardar o bloqueio quando ``wait`` é True. Quando
        ``wait`` é False a tentativa é não bloqueante e este valor é ignorado
        (uma ``LockTimeout`` imediata será levantada se o arquivo já estiver
        bloqueado).
    wait : bool
        Se ``True`` bloqueia até que o bloqueio esteja disponível ou que
        ``timeout_seconds`` expire. ``False`` faz a chamada falhar
        imediatamente se o bloqueio estiver em uso por outro processo.

    Yields
    ------
    dict
        Dicionário informativo com uma única chave ``lock_action`` (sempre
        "acquired" quando o corpo do contexto é executado) e
        ``lock_waited_seconds`` (float). Timeouts são reportados lançando
        a exceção :class:`LockTimeout` em vez de retornar uma ação distinta.

    Raises
    ------
    LockTimeout
        Quando o bloqueio não pode ser adquirido no modo solicitado. Este é o
        mecanismo pelo qual os chamadores observam timeouts ou falhas
        não bloqueantes.
    """

    # respeita a variável de ambiente explícita, permite expansão de ~ e resolve
    # para um caminho absoluto
    lock_dir = _resolve_lock_dir(os.environ.get("LOCK_DIR"))
    lock_dir.mkdir(parents=True, exist_ok=True)
    # normalize ticker for filesystem: try canonical B3 form first
    try:
        norm = normalize_b3_ticker(ticker)
    except Exception:
        # non-B3 or invalid symbol; fall back to uppercase
        norm = ticker.strip().upper()
    import re

    safe = re.sub(r"[^A-Z0-9._-]", "_", norm)
    if not safe or safe.lower() != norm.lower():
        # if normalization removed too much or changed case, hash to avoid
        # collisions and keep filename reasonable length
        import hashlib

        h = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:8]
        safe = f"{safe or 'T'}_{h}"
    lock_path = lock_dir / f"{safe}.lock"

    # abre o descritor de arquivo agora para que ele permaneça válido até o
    # fim do contexto ou até desistirmos de adquirir o bloqueio. Se a
    # aquisição falhar precisamos fechar o descritor imediatamente para evitar
    # vazamentos de recursos.
    fh = open(lock_path, "a+")
    start = time.monotonic()

    # Adquire o bloqueio usando o backend preferido. Se a aquisição falhar,
    # uma exceção é levantada e ``fh`` é fechado imediatamente no ``finally``
    # abaixo. Isso mantém o caminho feliz limpo e evita uma flag ``locked``
    # explícita.
    try:
        if portalocker is not None:
            flags = portalocker.LockFlags.EXCLUSIVE
            if not wait:
                flags |= portalocker.LockFlags.NON_BLOCKING
            _acquire_with_portalocker(
                fh, flags, wait, timeout_seconds, start, ticker
            )
        else:
            _acquire_with_fcntl(fh, wait, timeout_seconds, start, ticker)

        waited = time.monotonic() - start
        try:
            yield {"lock_action": "acquired", "lock_waited_seconds": waited}
        finally:
            # libera o bloqueio (melhor esforço, engole quaisquer erros)
            try:
                if portalocker is not None:
                    portalocker.unlock(fh)
                else:
                    import fcntl

                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except Exception as exc:  # pragma: no cover - melhor esforço
                # liberar um bloqueio não é crítico para os chamadores, mas falhar
                # ao destravar pode levar a arquivos presos em produção. Logue em
                # nível warning/debug para que operadores possam investigar depois.
                logger.warning("falha ao liberar bloqueio para %s: %s", ticker, exc)
    finally:
        # sempre fecha o descritor de arquivo, mesmo se a aquisição falhar
        fh.close()

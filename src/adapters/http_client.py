"""Abstração mínima de cliente HTTP usada para facilitar mocks em testes.

Este módulo fornece um protocolo simples e um adaptador baseado em
`requests` quando disponível. Importações pesadas são feitas sob demanda
para não causar falhas em ambientes de teste sem dependências.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol


class HTTPClientProtocol(Protocol):
    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:  # pragma: no cover - interface
        ...


class RequestsHTTPClient:
    """Implementação baseada em `requests` (lazy import).

    Usa importação local para evitar falha de import se `requests` não
    estiver instalado em ambientes de teste isolados.
    """

    def __init__(self):
        try:
            import requests  # type: ignore

            self._requests = requests
        except Exception as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "requests library is required for RequestsHTTPClient"
            ) from exc

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        resp = self._requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp


def get_default_client() -> HTTPClientProtocol:
    """Retorna uma implementação padrão do cliente HTTP.

    Atualmente mapeia para `RequestsHTTPClient`. Chamadas a essa função
    apenas resolvem a implementação em tempo de execução.
    """
    return RequestsHTTPClient()

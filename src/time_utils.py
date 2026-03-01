"""Utilitários de data/hora UTC para o projeto.

Funções auxiliares leves para obter o instante atual em UTC
(:func:`now_utc_iso`) e converter parâmetros flexíveis de data para o formato
ISO 8601 (:func:`to_iso_date`).  Nenhuma dependência externa além da stdlib.
"""

from datetime import date, datetime, timezone
from typing import Optional, Union


def now_utc_iso() -> str:
    """Retorna o datetime UTC atual em formato ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


def to_iso_date(d: Optional[Union[str, date, datetime]]) -> Optional[str]:
    """Normaliza um valor date/datetime/str para a string "YYYY-MM-DD".

    Parâmetros:
        d (Optional[Union[str, date, datetime]]): valor a normalizar. Se
            for `None`, retorna `None`.

    Retorno:
        Optional[str]: string no formato `YYYY-MM-DD` ou `None` quando a
        entrada for `None`.
    """
    if d is None:
        return None
    if isinstance(d, str):
        # Valida que a string esteja no formato ISO YYYY-MM-DD
        try:
            parsed = datetime.strptime(d, "%Y-%m-%d")
        except ValueError as exc:
            msg = "string de data deve estar no formato YYYY-MM-DD: " + repr(d)
            raise ValueError(msg) from exc
        return parsed.strftime("%Y-%m-%d")
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m-%d")
    raise TypeError("Tipo de data não suportado para to_iso_date")

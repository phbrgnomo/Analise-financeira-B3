"""Funções utilitárias de conversão compartilhadas entre módulos.

Centraliza helpers que são usados por mais de um módulo para evitar
duplicação (DRY).
"""


def as_bool(value: object) -> bool:
    """Converte valor potencialmente serializado pela CLI em booleano.

    Aceita ``bool``, ``str`` (``"1"``, ``"true"``, ``"yes"``, ``"on"``
    são truthy) e qualquer outro tipo via ``bool(value)``.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)

"""
Deprecatado — o módulo existe apenas para compatibilidade com código
ancestral.  Todos os consumidores novos devem trocar por
``factory.get_adapter(provider).fetch(...)``.

As funções aqui são meros wrappers que emitam ``DeprecationWarning`` e
redirigem para a fábrica.  O restante da implementação histórica foi
removido para reduzir a superfície de manutenção.
"""

import warnings

from src.adapters.factory import get_adapter

# importing this module is deprecated; emit once per import
warnings.warn(
    "src.dados_b3 is deprecated; use src.adapters.factory.get_adapter instead",
    DeprecationWarning,
    stacklevel=2,
)


def cotacao_indice_dia(indice, data_inicio, data_fim, provider: str | None = None):
    """Deprecated wrapper. Use factory.get_adapter(...).fetch() directly.

    Emite :class:`DeprecationWarning`.
    """
    warnings.warn(
        "cotacao_indice_dia is deprecated; call an adapter directly",
        DeprecationWarning,
        stacklevel=2,
    )
    adapter = get_adapter(provider or "yfinance")
    return adapter.fetch(f"^{indice}", start_date=data_inicio, end_date=data_fim)


def cotacao_ativo_dia(ativo, data_inicio, data_fim, provider: str | None = None):
    """Deprecated wrapper. Use factory.get_adapter(...).fetch() directly.

    Emite :class:`DeprecationWarning`.
    """
    warnings.warn(
        "cotacao_ativo_dia is deprecated; call an adapter directly",
        DeprecationWarning,
        stacklevel=2,
    )
    adapter = get_adapter(provider or "yfinance")
    return adapter.fetch(
        f"{ativo}.SA",
        start_date=f"{data_inicio}",
        end_date=f"{data_fim}",
    )

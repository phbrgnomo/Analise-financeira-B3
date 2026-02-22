"""
Módulo de adaptadores para provedores de dados financeiros.

Este módulo fornece interfaces abstratas e implementações concretas
para buscar dados de mercado de diferentes provedores.
"""

from src.adapters.base import Adapter
from src.adapters.errors import AdapterError
from src.adapters.yfinance_adapter import YFinanceAdapter

__all__ = ["Adapter", "AdapterError", "YFinanceAdapter"]

"""
Interface base para adaptadores de provedores de dados financeiros.

Define o contrato público que todos os adaptadores devem implementar.
"""

from abc import ABC, abstractmethod
from typing import Dict

import pandas as pd


class Adapter(ABC):
    """
    Interface abstrata para adaptadores de provedores de dados financeiros.

    Todos os adaptadores concretos devem herdar desta classe e implementar
    o método fetch() para buscar dados de um ticker específico.

    O adaptador é responsável apenas por buscar dados brutos do provedor,
    sem realizar persistência ou transformações complexas.
    """

    @abstractmethod
    def fetch(self, ticker: str, **kwargs) -> pd.DataFrame:
        """
        Busca dados brutos para um ticker do provedor.

        Args:
            ticker: Código do ativo (ex: 'PETR4' para B3, 'AAPL' para NYSE)
            **kwargs: Parâmetros adicionais específicos do provedor
                      (ex: start_date, end_date, period)

        Returns:
            pd.DataFrame: DataFrame com dados OHLCV do provedor.
                         Deve conter pelo menos as colunas:
                         ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
                         O DataFrame deve ter um índice DatetimeIndex.

        Raises:
            AdapterError: Erro genérico do adaptador
            FetchError: Falha ao buscar dados do provedor
            NetworkError: Erro de conectividade
            ValidationError: Dados retornados não possuem formato esperado
            RateLimitError: Limite de requisições atingido

        Notes:
            - Adaptador deve adicionar metadado 'source' ao DataFrame.attrs
            - Timestamps devem ser normalizados para UTC quando possível
            - Não realiza persistência; apenas retorna dados brutos
        """
        pass

    def get_metadata(self) -> Dict[str, str]:
        """
        Retorna metadados do adaptador.

        Returns:
            Dict com informações do provedor:
            - 'provider': Nome do provedor (ex: 'yahoo', 'alphavantage')
            - 'version': Versão da biblioteca usada
            - 'adapter_version': Versão do adaptador
        """
        return {
            "provider": self.__class__.__name__.replace("Adapter", "").lower(),
            "adapter_version": "1.0.0",
        }

"""
Erros e exceções personalizadas para adaptadores de dados.

Define hierarquia de erros para tratamento padronizado de falhas
em provedores de dados financeiros.
"""

from typing import Optional


class AdapterError(Exception):
    """
    Erro base para falhas em adaptadores de dados.

    Attributes:
        message: Mensagem descritiva do erro
        code: Código do erro para categorização
        original_exception: Exceção original que causou o erro (opcional)
    """

    def __init__(
        self,
        message: str,
        code: str = "ADAPTER_ERROR",
        original_exception: Optional[BaseException] = None,
    ):
        """
        Inicializa AdapterError.

        Args:
            message: Descrição legível do erro
            code: Código identificador do tipo de erro
            original_exception: Exceção que originou este erro (se aplicável)
        """
        self.message = message
        self.code = code
        self.original_exception = original_exception
        super().__init__(self.message)

    def __str__(self):
        """Retorna representação string do erro."""
        if self.original_exception:
            return (
                f"[{self.code}] {self.message} (caused by: {self.original_exception})"  # noqa: E501
            )
        return f"[{self.code}] {self.message}"


class FetchError(AdapterError):
    """Erro ao buscar dados do provedor."""

    def __init__(
        self,
        message: str,
        original_exception: Optional[BaseException] = None,
    ):
        super().__init__(
            message, code="FETCH_ERROR", original_exception=original_exception
        )


class ValidationError(AdapterError):
    """Erro de validação de dados retornados pelo provedor."""

    def __init__(
        self,
        message: str,
        original_exception: Optional[BaseException] = None,
    ):
        super().__init__(
            message, code="VALIDATION_ERROR", original_exception=original_exception
        )


class NetworkError(AdapterError):
    """Erro de rede ao acessar provedor."""

    def __init__(
        self,
        message: str,
        original_exception: Optional[BaseException] = None,
    ):
        super().__init__(
            message, code="NETWORK_ERROR", original_exception=original_exception
        )


class RateLimitError(AdapterError):
    """Erro quando limite de requisições do provedor é atingido."""

    def __init__(
        self,
        message: str,
        original_exception: Optional[BaseException] = None,
    ):
        super().__init__(
            message, code="RATE_LIMIT_ERROR", original_exception=original_exception
        )

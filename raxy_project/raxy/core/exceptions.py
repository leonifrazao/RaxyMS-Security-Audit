"""Sistema centralizado de exceções customizadas do Raxy."""

from __future__ import annotations
from typing import Any, Optional


class RaxyBaseException(Exception):
    """Exceção base para todas as exceções customizadas do Raxy."""
    
    def __init__(self, message: str, *, details: Optional[dict[str, Any]] = None, cause: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.cause = cause
    
    def __str__(self) -> str:
        base = self.message
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            base = f"{base} ({details_str})"
        if self.cause:
            base = f"{base} | Causa: {self.cause}"
        return base
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, details={self.details!r})"


# ==================== Exceções de Rede ====================

class NetworkException(RaxyBaseException):
    """Exceção base para erros relacionados à rede."""
    pass


class ProxyException(NetworkException):
    """Exceções relacionadas a proxies."""
    pass


class ProxyRotationRequiredException(ProxyException):
    """Sinaliza necessidade de rotacionar a proxy quando um erro HTTP 400+ ocorre."""
    
    def __init__(self, status_code: int, proxy_id: str | int | None = None, url: Optional[str] = None):
        self.status_code = status_code
        self.proxy_id = proxy_id
        self.url = url
        details = {"status_code": status_code, "proxy_id": proxy_id}
        if url:
            details["url"] = url
        super().__init__(
            f"Erro HTTP {status_code} — rotacionar proxy (ID: {proxy_id})",
            details=details
        )


class ProxyConnectionException(ProxyException):
    """Erro ao conectar através da proxy."""
    pass


class ProxyTimeoutException(ProxyException):
    """Timeout ao usar proxy."""
    pass


class RequestException(NetworkException):
    """Erro em requisição HTTP."""
    pass


class RequestTimeoutException(RequestException):
    """Timeout em requisição HTTP."""
    pass


class InvalidResponseException(RequestException):
    """Resposta HTTP inválida ou malformada."""
    pass


# ==================== Exceções de Autenticação ====================

class AuthenticationException(RaxyBaseException):
    """Exceção base para erros de autenticação."""
    pass


class LoginException(AuthenticationException):
    """Erro durante o processo de login."""
    pass


class InvalidCredentialsException(AuthenticationException):
    """Credenciais inválidas."""
    pass


class AccountLockedException(AuthenticationException):
    """Conta bloqueada ou suspensa."""
    pass


class CaptchaRequiredException(AuthenticationException):
    """CAPTCHA detectado."""
    pass


class TwoFactorRequiredException(AuthenticationException):
    """Autenticação de dois fatores necessária."""
    pass


# ==================== Exceções de Sessão ====================

class SessionException(RaxyBaseException):
    """Exceção base para erros de sessão."""
    pass


class SessionExpiredException(SessionException):
    """Sessão expirou."""
    pass


class SessionNotInitializedException(SessionException):
    """Sessão não foi inicializada."""
    pass


class CookieException(SessionException):
    """Erro relacionado a cookies."""
    pass


class TokenException(SessionException):
    """Erro relacionado a tokens de verificação."""
    pass


# ==================== Exceções de API ====================

class APIException(RaxyBaseException):
    """Exceção base para erros de API."""
    pass


class RewardsAPIException(APIException):
    """Erro na API do Microsoft Rewards."""
    pass


class BingAPIException(APIException):
    """Erro na API do Bing."""
    pass


class MailTmAPIException(APIException):
    """Erro na API do Mail.tm."""
    pass


class InvalidAPIResponseException(APIException):
    """Resposta de API inválida ou inesperada."""
    pass


class RateLimitException(APIException):
    """Rate limit atingido."""
    pass


# ==================== Exceções de Parsing ====================

class ParsingException(RaxyBaseException):
    """Exceção base para erros de parsing."""
    pass


class HTMLParsingException(ParsingException):
    """Erro ao fazer parse de HTML."""
    pass


class JSONParsingException(ParsingException):
    """Erro ao fazer parse de JSON."""
    pass


class DataExtractionException(ParsingException):
    """Erro ao extrair dados."""
    pass


# ==================== Exceções de Configuração ====================

class ConfigurationException(RaxyBaseException):
    """Exceção base para erros de configuração."""
    pass


class InvalidConfigException(ConfigurationException):
    """Configuração inválida."""
    pass


class MissingConfigException(ConfigurationException):
    """Configuração obrigatória ausente."""
    pass


class ProfileException(ConfigurationException):
    """Erro relacionado a perfis."""
    pass


# ==================== Exceções de Repositório ====================

class RepositoryException(RaxyBaseException):
    """Exceção base para erros de repositório."""
    pass


class DatabaseException(RepositoryException):
    """Exceção para erros de banco de dados."""
    pass


class DataNotFoundException(RepositoryException):
    """Dados não encontrados."""
    pass


class DataValidationException(RepositoryException):
    """Erro de validação de dados."""
    pass


class FileRepositoryException(RepositoryException):
    """Erro em operações de arquivo."""
    pass


# ==================== Exceções de Browser ====================

class BrowserException(RaxyBaseException):
    """Exceção base para erros do browser."""
    pass


class ElementNotFoundException(BrowserException):
    """Elemento não encontrado na página."""
    pass


class PageLoadException(BrowserException):
    """Erro ao carregar página."""
    pass


class BrowserCrashException(BrowserException):
    """Browser travou ou foi fechado inesperadamente."""
    pass


class JavaScriptException(BrowserException):
    """Erro ao executar JavaScript."""
    pass


# ==================== Exceções de Execução ====================

class ExecutionException(RaxyBaseException):
    """Exceção base para erros de execução."""
    pass


class TaskExecutionException(ExecutionException):
    """Erro ao executar tarefa."""
    pass


class TimeoutException(ExecutionException):
    """Operação excedeu tempo limite."""
    pass


class RetryExhaustedException(ExecutionException):
    """Todas as tentativas de retry foram esgotadas."""
    
    def __init__(self, attempts: int, last_error: Optional[Exception] = None):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"Todas as {attempts} tentativas falharam",
            details={"attempts": attempts, "last_error": str(last_error) if last_error else None},
            cause=last_error
        )


# ==================== Exceções de Validação ====================

class ValidationException(RaxyBaseException):
    """Exceção base para erros de validação."""
    pass


class InvalidInputException(ValidationException):
    """Input inválido."""
    pass


class MissingRequiredFieldException(ValidationException):
    """Campo obrigatório ausente."""
    pass


# ==================== Exceções de Recursos ====================

class ResourceException(RaxyBaseException):
    """Exceção base para erros de recursos."""
    pass


class ResourceNotFoundException(ResourceException):
    """Recurso não encontrado."""
    pass


class ResourceUnavailableException(ResourceException):
    """Recurso temporariamente indisponível."""
    pass


class DependencyException(ResourceException):
    """Dependência necessária não disponível."""
    pass


# ==================== Helpers ====================

def wrap_exception(exc: Exception, wrapper_class: type[RaxyBaseException], message: str, **details: Any) -> RaxyBaseException:
    """
    Envolve uma exceção existente em uma exceção customizada.
    
    Args:
        exc: Exceção original
        wrapper_class: Classe da exceção customizada
        message: Mensagem descritiva
        **details: Detalhes adicionais
    
    Returns:
        Instância da exceção customizada
    """
    return wrapper_class(message, details=details, cause=exc)


__all__ = [
    # Base
    "RaxyBaseException",
    # Network
    "NetworkException",
    "ProxyException",
    "ProxyRotationRequiredException",
    "ProxyConnectionException",
    "ProxyTimeoutException",
    "RequestException",
    "RequestTimeoutException",
    "InvalidResponseException",
    # Authentication
    "AuthenticationException",
    "LoginException",
    "InvalidCredentialsException",
    "AccountLockedException",
    "CaptchaRequiredException",
    "TwoFactorRequiredException",
    # Session
    "SessionException",
    "SessionExpiredException",
    "SessionNotInitializedException",
    "CookieException",
    "TokenException",
    # API
    "APIException",
    "RewardsAPIException",
    "BingAPIException",
    "MailTmAPIException",
    "InvalidAPIResponseException",
    "RateLimitException",
    # Parsing
    "ParsingException",
    "HTMLParsingException",
    "JSONParsingException",
    "DataExtractionException",
    # Configuration
    "ConfigurationException",
    "InvalidConfigException",
    "MissingConfigException",
    "ProfileException",
    # Repository
    "RepositoryException",
    "DataNotFoundException",
    "DataValidationException",
    "FileRepositoryException",
    # Browser
    "BrowserException",
    "ElementNotFoundException",
    "PageLoadException",
    "BrowserCrashException",
    "JavaScriptException",
    # Execution
    "ExecutionException",
    "TaskExecutionException",
    "TimeoutException",
    "RetryExhaustedException",
    # Validation
    "ValidationException",
    "InvalidInputException",
    "MissingRequiredFieldException",
    # Resources
    "ResourceException",
    "ResourceNotFoundException",
    "ResourceUnavailableException",
    "DependencyException",
    # Helpers
    "wrap_exception",
]

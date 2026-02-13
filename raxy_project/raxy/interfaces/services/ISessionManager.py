"""Interface para gerenciamento de sessões."""

from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Mapping, Optional

from raxy.models.accounts import Conta
from raxy.interfaces.webdrivers import IBrowserDriver


class ISessionManager(ABC):
    """
    Interface para gerenciamento de sessões de navegação.
    
    Define o contrato para serviços que gerenciam sessões de browser,
    incluindo login, cookies, user-agent e execução de templates.
    
    Note:
        As properties cookies, user_agent e token_antifalsificacao podem ser
        implementadas como properties ou atributos de instância.
        O importante é que sejam acessíveis como atributos públicos.
    """
    
    # Atributos que devem existir (mas não forçamos como @abstractmethod)
    # pois podem ser atributos de instância simples
    driver: Optional[IBrowserDriver]
    conta: Conta
    
    # Properties com lógica (implementadas com @property no SessionManager)
    # Não marcamos como @abstractmethod para permitir implementação flexível
    
    # Métodos abstratos
    @abstractmethod
    def start(self) -> None:
        """
        Inicia a sessão (login, configuração de driver).
        
        Raises:
            SessionException: Se erro ao iniciar sessão
        """
        ...

    @abstractmethod
    def refresh_session(self) -> None:
        """
        Executa fluxo de login para atualizar credenciais da sessão.
        """
        ...
    
    @abstractmethod
    def execute_template(
        self,
        template_path_or_dict: str | Path | Mapping[str, Any],
        *,
        placeholders: Mapping[str, Any] | None = None,
        use_ua: bool = True,
        use_cookies: bool = True,
        bypass_request_token: bool = True,
    ) -> Any:
        """
        Executa um template de requisição HTTP.
        
        Args:
            template_path_or_dict: Caminho ou dict do template
            placeholders: Valores para substituir no template
            use_ua: Se deve usar User-Agent da sessão
            use_cookies: Se deve usar cookies da sessão
            bypass_request_token: Se deve adicionar token de verificação
            
        Returns:
            Any: Resposta da requisição
            
        Raises:
            SessionException: Se sessão não estiver iniciada
        """
        ...
    
    @abstractmethod
    def close(self) -> None:
        """
        Fecha a sessão e libera recursos.
        """
        ...


__all__ = ['ISessionManager']

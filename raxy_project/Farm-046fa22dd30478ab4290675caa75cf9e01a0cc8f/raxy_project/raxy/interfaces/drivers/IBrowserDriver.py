"""
Interface para abstração de drivers de navegador.

Define o contrato que qualquer implementação de driver (Botasaurus, Selenium,
Playwright, etc.) deve seguir para garantir desacoplamento.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional


class IBrowserDriver(ABC):
    """
    Interface abstrata para drivers de navegador.
    
    Esta interface define as operações essenciais que qualquer driver
    de navegador deve implementar, permitindo trocar implementações
    sem modificar o código cliente.
    
    Princípios:
    - Dependency Inversion Principle (DIP)
    - Open/Closed Principle (OCP)
    - Interface Segregation Principle (ISP)
    """
    
    # ========== Navegação ==========
    
    @abstractmethod
    def google_get(self, url: str, **kwargs) -> None:
        """
        Navega para uma URL de forma otimizada (Google-style).
        
        Args:
            url: URL de destino
            **kwargs: Argumentos adicionais específicos da implementação
        """
        pass
    
    @abstractmethod
    def get_current_url(self) -> str:
        """
        Retorna a URL atual da página.
        
        Returns:
            str: URL atual
        """
        pass
    
    # ========== Interação com Elementos ==========
    
    @abstractmethod
    def click(self, selector: str, wait: Optional[int] = None, **kwargs) -> None:
        """
        Clica em um elemento.
        
        Args:
            selector: Seletor CSS/XPath do elemento
            wait: Tempo de espera em segundos
            **kwargs: Argumentos adicionais
        """
        pass
    
    @abstractmethod
    def type(self, selector: str, text: str, wait: Optional[int] = None, **kwargs) -> None:
        """
        Digita texto em um elemento.
        
        Args:
            selector: Seletor CSS/XPath do elemento
            text: Texto a ser digitado
            wait: Tempo de espera em segundos
            **kwargs: Argumentos adicionais
        """
        pass
    
    @abstractmethod
    def is_element_present(self, selector: str, wait: Optional[int] = None) -> bool:
        """
        Verifica se um elemento está presente na página.
        
        Args:
            selector: Seletor CSS/XPath do elemento
            wait: Tempo de espera em segundos
            
        Returns:
            bool: True se elemento está presente
        """
        pass
    
    # ========== Execução de JavaScript ==========
    
    @abstractmethod
    def run_js(self, script: str, *args, **kwargs) -> Any:
        """
        Executa JavaScript no contexto da página.
        
        Args:
            script: Código JavaScript a executar
            *args: Argumentos posicionais
            **kwargs: Argumentos nomeados
            
        Returns:
            Any: Resultado da execução
        """
        pass
    
    # ========== Gerenciamento de Sessão ==========
    
    @abstractmethod
    def get_cookies(self) -> Dict[str, str]:
        """
        Obtém todos os cookies da sessão atual.
        
        Returns:
            Dict[str, str]: Dicionário de cookies (nome: valor)
        """
        pass
    
    @abstractmethod
    def get_user_agent(self) -> str:
        """
        Obtém o User-Agent atual do navegador.
        
        Returns:
            str: String do User-Agent
        """
        pass
    
    @abstractmethod
    def get_profile_data(self, key: str, default: Any = None) -> Any:
        """
        Obtém dados do perfil do navegador.
        
        Args:
            key: Chave do dado
            default: Valor padrão se não encontrado
            
        Returns:
            Any: Valor do dado
        """
        pass
    
    # ========== Comportamento Humano ==========
    
    @abstractmethod
    def enable_human_mode(self) -> None:
        """
        Ativa modo de comportamento humano (delays aleatórios, movimentos, etc.).
        """
        pass
    
    @abstractmethod
    def short_random_sleep(self, min_seconds: float = 0.5, max_seconds: float = 2.0) -> None:
        """
        Aguarda um tempo aleatório curto (simula comportamento humano).
        
        Args:
            min_seconds: Tempo mínimo em segundos
            max_seconds: Tempo máximo em segundos
        """
        pass
    
    # ========== Monitoramento de Rede ==========
    
    @abstractmethod
    def after_response_received(self, callback: Callable) -> None:
        """
        Registra callback para interceptar respostas de rede.
        
        Args:
            callback: Função a ser chamada após cada resposta
        """
        pass
    
    # ========== Lifecycle ==========
    
    @abstractmethod
    def quit(self) -> None:
        """
        Fecha o navegador e libera recursos.
        """
        pass
    
    @abstractmethod
    def is_active(self) -> bool:
        """
        Verifica se o driver ainda está ativo.
        
        Returns:
            bool: True se ativo
        """
        pass
    
    # ========== Propriedades ==========
    
    @property
    @abstractmethod
    def current_url(self) -> str:
        """URL atual (propriedade)."""
        pass
    
    @property
    @abstractmethod
    def config(self) -> Any:
        """Configuração do driver (específica da implementação)."""
        pass
    
    @property
    @abstractmethod
    def profile(self) -> Dict[str, Any]:
        """Perfil do navegador."""
        pass

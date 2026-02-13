"""
Implementação do IBrowserDriver usando Botasaurus.

Adapter que envolve o Driver do Botasaurus para seguir a interface padronizada,
permitindo trocar a implementação sem impactar o código cliente.
"""

from __future__ import annotations
from typing import Any, Callable, Dict, Optional
from botasaurus.browser import Driver

from raxy.core.logging import get_logger

from raxy.interfaces.webdrivers import IBrowserDriver


class BotasaurusDriver(IBrowserDriver):
    """
    Adapter para o Driver do Botasaurus.
    
    Implementa IBrowserDriver delegando chamadas para o Driver do Botasaurus,
    seguindo o padrão Adapter para desacoplamento.
    
    Design Pattern: Adapter Pattern
    Princípio: Dependency Inversion Principle (DIP)
    """
    
    def __init__(self, driver: Driver):
        """
        Inicializa o adapter.
        
        Args:
            driver: Instância do Driver do Botasaurus
        """
        self._driver = driver
        self.logger = get_logger()
    
    # ========== Navegação ==========
    
    def google_get(self, url: str, **kwargs) -> None:
        """Navega para URL usando método otimizado do Botasaurus."""
        self.logger.debug(f"Botasaurus navigando para: {url}")
        self._driver.google_get(url, **kwargs)
    
    def get_current_url(self) -> str:
        """Retorna URL atual."""
        return self._driver.current_url
    
    # ========== Interação com Elementos ==========
    
    def click(self, selector: str, wait: Optional[int] = None, **kwargs) -> None:
        """Clica em elemento."""
        self._driver.click(selector, wait=wait, **kwargs)
    
    def type(self, selector: str, text: str, wait: Optional[int] = None, **kwargs) -> None:
        """Digita texto em elemento."""
        self._driver.type(selector, text, wait=wait, **kwargs)
    
    def is_element_present(self, selector: str, wait: Optional[int] = None) -> bool:
        """Verifica presença de elemento."""
        return self._driver.is_element_present(selector, wait=wait)
    
    # ========== Execução de JavaScript ==========
    
    def run_js(self, script: str, *args, **kwargs) -> Any:
        """Executa JavaScript."""
        return self._driver.run_js(script, *args, **kwargs)
    
    # ========== Gerenciamento de Sessão ==========
    
    def get_cookies(self) -> Dict[str, str]:
        """
        Obtém cookies da sessão.
        
        Returns:
            Dict[str, str]: Cookies no formato {nome: valor}
        """
        cookies_list = self._driver.get_cookies_dict()
        if isinstance(cookies_list, dict):
            return cookies_list
        # Se retornar lista, converte para dict
        return {cookie['name']: cookie['value'] for cookie in cookies_list}
    
    def get_user_agent(self) -> str:
        """Obtém User-Agent."""
        return self._driver.run_js("return navigator.userAgent;")
    
    def get_profile_data(self, key: str, default: Any = None) -> Any:
        """Obtém dados do perfil."""
        return self._driver.profile.get(key, default)
    
    # ========== Comportamento Humano ==========
    
    def enable_human_mode(self) -> None:
        """Ativa modo humano."""
        self._driver.enable_human_mode()
    
    def short_random_sleep(self, min_seconds: float = 0.5, max_seconds: float = 2.0) -> None:
        """Sleep aleatório curto."""
        self._driver.short_random_sleep()
    
    # ========== Monitoramento de Rede ==========
    
    def after_response_received(self, callback: Callable) -> None:
        """Registra callback para respostas de rede."""
        self._driver.after_response_received(callback)
    
    # ========== Lifecycle ==========
    
    def quit(self) -> None:
        """Fecha navegador."""
        if self._driver:
            self._driver.quit()
    
    def is_active(self) -> bool:
        """Verifica se driver está ativo."""
        try:
            # Tenta executar comando simples para verificar se está ativo
            self._driver.current_url
            return True
        except Exception:
            return False
    
    # ========== Propriedades ==========
    
    @property
    def current_url(self) -> str:
        """URL atual."""
        return self._driver.current_url
    
    @property
    def config(self) -> Any:
        """Configuração do driver."""
        return self._driver.config
    
    @property
    def profile(self) -> Dict[str, Any]:
        """Perfil do navegador."""
        return self._driver.profile
    
    # ========== Acesso ao Driver Nativo (para casos especiais) ==========
    
    def get_native_driver(self) -> Driver:
        """
        Retorna o driver nativo do Botasaurus.
        
        NOTA: Use apenas quando absolutamente necessário.
        Evite vazamento de abstração (Leaky Abstraction).
        
        Returns:
            Driver: Driver nativo do Botasaurus
        """
        return self._driver

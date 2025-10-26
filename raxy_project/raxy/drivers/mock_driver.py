"""
Mock Driver para testes unitários.

Implementação fake do IBrowserDriver que permite testar
componentes sem necessidade de navegador real.
"""

from __future__ import annotations
from typing import Any, Callable, Dict, Optional
from unittest.mock import MagicMock

from raxy.interfaces.drivers import IBrowserDriver


class MockDriver(IBrowserDriver):
    """
    Driver mock para testes unitários.
    
    Implementa IBrowserDriver sem abrir navegador real,
    permitindo testes rápidos e determinísticos.
    
    Design Pattern: Test Double (Mock Object)
    Uso: Testes unitários
    """
    
    def __init__(
        self,
        cookies: Optional[Dict[str, str]] = None,
        user_agent: str = "MockUserAgent/1.0",
        profile_data: Optional[Dict[str, Any]] = None,
        url: str = "https://example.com"
    ):
        """
        Inicializa o mock driver.
        
        Args:
            cookies: Cookies fake para retornar
            user_agent: User-Agent fake
            profile_data: Dados do perfil
            url: URL atual simulada
        """
        self._cookies = cookies or {}
        self._user_agent = user_agent
        self._profile = profile_data or {}
        self._current_url = url
        self._is_active = True
        self._js_results: Dict[str, Any] = {}
        self._elements_present: Dict[str, bool] = {}
        
        # Mock config
        self._config = MagicMock()
        self._config.profile = self._profile
        
        # Rastreamento de chamadas para assertions
        self.calls: Dict[str, list] = {
            "google_get": [],
            "click": [],
            "type": [],
            "run_js": [],
        }
    
    # ========== Navegação ==========
    
    def google_get(self, url: str, **kwargs) -> None:
        """Simula navegação."""
        self._current_url = url
        self.calls["google_get"].append({"url": url, "kwargs": kwargs})
    
    def get_current_url(self) -> str:
        """Retorna URL mock."""
        return self._current_url
    
    # ========== Interação com Elementos ==========
    
    def click(self, selector: str, wait: Optional[int] = None, **kwargs) -> None:
        """Simula clique."""
        self.calls["click"].append({"selector": selector, "wait": wait, "kwargs": kwargs})
    
    def type(self, selector: str, text: str, wait: Optional[int] = None, **kwargs) -> None:
        """Simula digitação."""
        self.calls["type"].append({
            "selector": selector,
            "text": text,
            "wait": wait,
            "kwargs": kwargs
        })
    
    def is_element_present(self, selector: str, wait: Optional[int] = None) -> bool:
        """Retorna se elemento está presente (configurável)."""
        return self._elements_present.get(selector, True)
    
    # ========== Execução de JavaScript ==========
    
    def run_js(self, script: str, *args, **kwargs) -> Any:
        """Simula execução de JavaScript."""
        self.calls["run_js"].append({"script": script, "args": args, "kwargs": kwargs})
        # Retorna resultado pré-configurado ou None
        return self._js_results.get(script, None)
    
    # ========== Gerenciamento de Sessão ==========
    
    def get_cookies(self) -> Dict[str, str]:
        """Retorna cookies mock."""
        return self._cookies.copy()
    
    def get_user_agent(self) -> str:
        """Retorna User-Agent mock."""
        return self._user_agent
    
    def get_profile_data(self, key: str, default: Any = None) -> Any:
        """Retorna dados do perfil."""
        return self._profile.get(key, default)
    
    # ========== Comportamento Humano ==========
    
    def enable_human_mode(self) -> None:
        """Simula ativação de modo humano."""
        pass
    
    def short_random_sleep(self, min_seconds: float = 0.5, max_seconds: float = 2.0) -> None:
        """Simula sleep (não faz nada para testes rápidos)."""
        pass
    
    # ========== Monitoramento de Rede ==========
    
    def after_response_received(self, callback: Callable) -> None:
        """Simula registro de callback."""
        pass
    
    # ========== Lifecycle ==========
    
    def quit(self) -> None:
        """Simula fechamento."""
        self._is_active = False
    
    def is_active(self) -> bool:
        """Retorna status ativo."""
        return self._is_active
    
    # ========== Propriedades ==========
    
    @property
    def current_url(self) -> str:
        """URL atual."""
        return self._current_url
    
    @property
    def config(self) -> Any:
        """Configuração mock."""
        return self._config
    
    @property
    def profile(self) -> Dict[str, Any]:
        """Perfil mock."""
        return self._profile
    
    # ========== Métodos de Configuração para Testes ==========
    
    def set_js_result(self, script: str, result: Any) -> None:
        """
        Configura resultado para script JavaScript.
        
        Args:
            script: Script JavaScript
            result: Resultado a retornar
        """
        self._js_results[script] = result
    
    def set_element_present(self, selector: str, present: bool) -> None:
        """
        Configura se elemento está presente.
        
        Args:
            selector: Seletor do elemento
            present: True se presente
        """
        self._elements_present[selector] = present
    
    def set_cookies(self, cookies: Dict[str, str]) -> None:
        """
        Configura cookies.
        
        Args:
            cookies: Dicionário de cookies
        """
        self._cookies = cookies.copy()
    
    def get_call_count(self, method: str) -> int:
        """
        Retorna número de vezes que método foi chamado.
        
        Args:
            method: Nome do método
            
        Returns:
            int: Número de chamadas
        """
        return len(self.calls.get(method, []))
    
    def assert_called(self, method: str, times: Optional[int] = None) -> bool:
        """
        Verifica se método foi chamado.
        
        Args:
            method: Nome do método
            times: Número esperado de chamadas (None = pelo menos uma)
            
        Returns:
            bool: True se asserção passou
            
        Raises:
            AssertionError: Se asserção falhou
        """
        call_count = self.get_call_count(method)
        
        if times is None:
            if call_count == 0:
                raise AssertionError(f"Expected '{method}' to be called, but it wasn't")
        else:
            if call_count != times:
                raise AssertionError(
                    f"Expected '{method}' to be called {times} time(s), "
                    f"but was called {call_count} time(s)"
                )
        
        return True

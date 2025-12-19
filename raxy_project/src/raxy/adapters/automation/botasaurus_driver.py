"""
Implementação do BrowserDriver usando Botasaurus.
"""

from __future__ import annotations
from typing import Any, Callable, Dict, Optional
from botasaurus.browser import Driver

from raxy.core.interfaces import BrowserDriverProtocol

class BotasaurusDriver:
    """Adapter para o Driver do Botasaurus."""
    
    def __init__(self, driver: Driver):
        self._driver = driver
    
    def google_get(self, url: str) -> None:
        """Navega para URL usando método otimizado."""
        self._driver.google_get(url)
    
    def get_current_url(self) -> str:
        return self._driver.current_url
    
    def click(self, selector: str, wait: Optional[int] = None) -> None:
        self._driver.click(selector, wait=wait)
    
    def type(self, selector: str, text: str, wait: Optional[int] = None) -> None:
        self._driver.type(selector, text, wait=wait)
    
    def is_element_present(self, selector: str, wait: Optional[int] = None) -> bool:
        return self._driver.is_element_present(selector, wait=wait)
    
    def run_js(self, script: str, *args, **kwargs) -> Any:
        return self._driver.run_js(script, *args, **kwargs)
    
    def get_cookies(self) -> Dict[str, str]:
        cookies_list = self._driver.get_cookies_dict()
        if isinstance(cookies_list, dict):
            return cookies_list
        return {cookie['name']: cookie['value'] for cookie in cookies_list}
    
    def get_user_agent(self) -> str:
        return self._driver.run_js("return navigator.userAgent;")
    
    def quit(self) -> None:
        if self._driver:
            self._driver.quit()
            
    # Métodos extras específicos do Botasaurus (não na interface, mas úteis)
    def short_random_sleep(self) -> None:
        self._driver.short_random_sleep()
    
    def enable_human_mode(self) -> None:
        self._driver.enable_human_mode()

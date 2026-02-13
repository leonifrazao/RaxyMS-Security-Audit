"""
Implementação do IBrowserDriver usando Selenium.

Adapter que permite usar Selenium como alternativa ao Botasaurus,
demonstrando o poder do desacoplamento arquitetural.
"""

from __future__ import annotations
import time
import random
from typing import Any, Dict, List, Optional, Callable

from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from raxy.interfaces.webdrivers import IBrowserDriver
from raxy.core.logging import get_logger


class SeleniumDriver(IBrowserDriver):
    """
    Adapter para Selenium WebDriver.
    
    Implementa IBrowserDriver usando Selenium, permitindo trocar
    entre Botasaurus e Selenium sem modificar código cliente.
    
    Design Pattern: Adapter Pattern
    Princípio: Dependency Inversion Principle (DIP)
    
    Benefícios:
    - Compatibilidade com infraestrutura Selenium existente
    - Suporte nativo para AWS Lambda (headless)
    - Maior comunidade e documentação
    """
    
    def __init__(
        self,
        driver: Optional[webdriver.Chrome | webdriver.Firefox] = None,
        profile_data: Optional[Dict[str, Any]] = None,
        headless: bool = False
    ):
        """
        Inicializa o adapter Selenium.
        
        Args:
            driver: Instância do Selenium WebDriver (se None, cria Chrome)
            profile_data: Dados do perfil (email, senha, UA, etc.)
            headless: Se deve executar em modo headless
        """
        self._profile = profile_data or {}
        self._config_data = {"profile": self._profile}
        self._human_mode = False
        self._callbacks: list[Callable] = []
        self.logger = get_logger()
        
        self.logger.debug("Inicializando SeleniumDriver", headless=headless, profile_user=self._profile.get("email"))
        
        if driver is None:
            # Cria Chrome WebDriver com configurações padrão
            options = webdriver.ChromeOptions()
            if headless:
                options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            
            # User-Agent customizado se fornecido
            if 'UA' in self._profile:
                options.add_argument(f'user-agent={self._profile["UA"]}')
            
            self._driver = webdriver.Chrome(options=options)
        else:
            self._driver = driver
    
    # ========== Navegação ==========
    
    def google_get(self, url: str, **kwargs) -> None:
        """Navega para URL."""
        self.logger.debug(f"Navegando para: {url}")
        try:
            self._driver.get(url)
            if self._human_mode:
                self.short_random_sleep()
        except Exception as e:
            self.logger.erro(f"Erro ao navegar para {url}", exception=e)
            raise
    
    def get_current_url(self) -> str:
        """Retorna URL atual."""
        return self._driver.current_url
    
    # ========== Interação com Elementos ==========
    
    def click(self, selector: str, wait: Optional[int] = None, **kwargs) -> None:
        """
        Clica em elemento.
        
        Args:
            selector: Seletor CSS
            wait: Tempo de espera em segundos (padrão: 10)
        """
        timeout = wait if wait is not None else 10
        
        
        try:
            element = WebDriverWait(self._driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            element.click()
            self.logger.debug(f"Clique realizado: {selector}")
            
            if self._human_mode:
                self.short_random_sleep()
        except TimeoutException:
            self.logger.aviso(f"Timeout ao tentar clicar: {selector}")
            raise NoSuchElementException(f"Elemento não encontrado ou não clicável: {selector}")
        except Exception as e:
            self.logger.erro(f"Erro ao clicar em {selector}", exception=e)
            raise
    
    def type(self, selector: str, text: str, wait: Optional[int] = None, **kwargs) -> None:
        """
        Digita texto em elemento.
        
        Args:
            selector: Seletor CSS
            text: Texto a digitar
            wait: Tempo de espera em segundos
        """
        timeout = wait if wait is not None else 10
        
        try:
            element = WebDriverWait(self._driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            element.clear()
            
            if self._human_mode:
                # Digita caractere por caractere com delay
                for char in text:
                    element.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.15))
            else:
                element.send_keys(text)
            
            if self._human_mode:
                self.short_random_sleep()
        except TimeoutException:
            raise NoSuchElementException(f"Elemento não encontrado: {selector}")
    
    def is_element_present(self, selector: str, wait: Optional[int] = None) -> bool:
        """
        Verifica se elemento está presente.
        
        Args:
            selector: Seletor CSS
            wait: Tempo de espera em segundos (padrão: 5)
            
        Returns:
            bool: True se elemento presente
        """
        timeout = wait if wait is not None else 5
        
        try:
            WebDriverWait(self._driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            return True
        except TimeoutException:
            return False
    
    # ========== Execução de JavaScript ==========
    
    def run_js(self, script: str, *args, **kwargs) -> Any:
        """
        Executa JavaScript.
        
        Args:
            script: Código JavaScript
            *args: Argumentos para o script
            
        Returns:
            Any: Resultado da execução
        """
        return self._driver.execute_script(script, *args)
    
    # ========== Gerenciamento de Sessão ==========
    
    def get_cookies(self) -> Dict[str, str]:
        """
        Obtém cookies da sessão.
        
        Returns:
            Dict[str, str]: Cookies no formato {nome: valor}
        """
        cookies_list = self._driver.get_cookies()
        return {cookie['name']: cookie['value'] for cookie in cookies_list}
    
    def get_user_agent(self) -> str:
        """
        Obtém User-Agent atual.
        
        Returns:
            str: String do User-Agent
        """
        return self.run_js("return navigator.userAgent;")
    
    def get_profile_data(self, key: str, default: Any = None) -> Any:
        """
        Obtém dados do perfil.
        
        Args:
            key: Chave do dado
            default: Valor padrão
            
        Returns:
            Any: Valor do dado
        """
        return self._profile.get(key, default)
    
    # ========== Comportamento Humano ==========
    
    def enable_human_mode(self) -> None:
        """
        Ativa modo de comportamento humano.
        
        Adiciona delays aleatórios e comportamento mais natural.
        """
        self._human_mode = True
    
    def short_random_sleep(self, min_seconds: float = 0.5, max_seconds: float = 2.0) -> None:
        """
        Sleep aleatório (simula comportamento humano).
        
        Args:
            min_seconds: Tempo mínimo
            max_seconds: Tempo máximo
        """
        time.sleep(random.uniform(min_seconds, max_seconds))
    
    # ========== Monitoramento de Rede ==========
    
    def after_response_received(self, callback: Callable) -> None:
        """
        Registra callback para respostas de rede.
        
        NOTA: Selenium não tem suporte nativo para interceptação de rede.
        Esta implementação armazena o callback mas não o executa.
        Para interceptação real, seria necessário usar Selenium Wire
        ou ferramentas adicionais.
        
        Args:
            callback: Função callback
        """
        self._callbacks.append(callback)
    
    # ========== Lifecycle ==========
    
    def quit(self) -> None:
        """Fecha navegador e libera recursos."""
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
    
    def is_active(self) -> bool:
        """
        Verifica se driver está ativo.
        
        Returns:
            bool: True se ativo
        """
        try:
            # Tenta acessar sessão para verificar se está ativo
            _ = self._driver.current_url
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
        return self._config_data
    
    @property
    def profile(self) -> Dict[str, Any]:
        """Perfil do navegador (não suportado nativamente no Selenium sem gestão externa)."""
        return {}
    
    # ========== Métodos Utilitários ==========
    
    def get_native_driver(self) -> WebDriver:
        """
        Retorna o driver nativo do Selenium.
        
        NOTA: Use apenas quando absolutamente necessário.
        Evite vazamento de abstração (Leaky Abstraction).
        
        Returns:
            WebDriver: Driver nativo do Selenium
        """
        return self._driver
    
    def take_screenshot(self, filename: str) -> bool:
        """
        Captura screenshot (funcionalidade extra do Selenium).
        
        Args:
            filename: Nome do arquivo
            
        Returns:
            bool: True se sucesso
        """
        try:
            return self._driver.save_screenshot(filename)
        except Exception:
            return False
    
    def maximize_window(self) -> None:
        """Maximiza janela do navegador."""
        try:
            self._driver.maximize_window()
        except Exception:
            pass

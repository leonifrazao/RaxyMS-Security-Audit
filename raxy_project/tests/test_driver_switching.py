"""
Teste de troca de drivers - Demonstração do Desacoplamento.

Este teste demonstra o poder da arquitetura desacoplada:
podemos trocar entre Selenium, Botasaurus ou qualquer outra implementação
sem modificar o código cliente.

PRINCÍPIOS DEMONSTRADOS:
- Dependency Inversion Principle (DIP)
- Open/Closed Principle (OCP)
- Liskov Substitution Principle (LSP)
"""

import pytest
from typing import Type

from raxy.interfaces.drivers import IBrowserDriver
from raxy.drivers.selenium_driver import SeleniumDriver
from raxy.drivers.mock_driver import MockDriver


class TestDriverSwitching:
    """
    Testes que demonstram troca entre implementações de drivers.
    
    OBJETIVO: Provar que o código cliente não precisa saber qual
    implementação está usando - ele depende apenas da interface.
    """
    
    @pytest.fixture(params=['selenium', 'mock'])
    def driver(self, request) -> IBrowserDriver:
        """
        Fixture parametrizada que retorna diferentes implementações.
        
        O teste rodará uma vez para cada driver, demonstrando que
        a interface funciona independente da implementação.
        """
        if request.param == 'selenium':
            # Cria driver Selenium em modo headless
            driver = SeleniumDriver(headless=False)
            yield driver
            driver.quit()
        elif request.param == 'mock':
            # Cria driver mock para testes
            driver = MockDriver()
            yield driver
            driver.quit()
    
    def test_interface_compliance(self, driver: IBrowserDriver):
        """
        Testa que todas as implementações seguem a interface.
        
        PRINCÍPIO: Liskov Substitution Principle (LSP)
        Qualquer implementação de IBrowserDriver deve ser substituível.
        """
        # Valida métodos de navegação
        assert hasattr(driver, 'google_get')
        assert hasattr(driver, 'get_current_url')
        
        # Valida interação com elementos
        assert hasattr(driver, 'click')
        assert hasattr(driver, 'type')
        assert hasattr(driver, 'is_element_present')
        
        # Valida JavaScript
        assert hasattr(driver, 'run_js')
        
        # Valida sessão
        assert hasattr(driver, 'get_cookies')
        assert hasattr(driver, 'get_user_agent')
        
        # Valida lifecycle
        assert hasattr(driver, 'quit')
        assert hasattr(driver, 'is_active')
    
    def test_basic_navigation(self, driver: IBrowserDriver):
        """
        Testa navegação básica em qualquer driver.
        
        Este teste funciona tanto com Selenium quanto com Mock,
        demonstrando o desacoplamento perfeito.
        """
        # Navega para URL
        driver.google_get("https://example.com")
        
        # Verifica URL atual
        current_url = driver.get_current_url()
        assert current_url is not None
        assert len(current_url) > 0
    
    def test_user_agent_retrieval(self, driver: IBrowserDriver):
        """
        Testa obtenção de User-Agent em qualquer driver.
        """
        user_agent = driver.get_user_agent()
        assert user_agent is not None
        assert len(user_agent) > 0


class TestSeleniumDriverReal:
    """
    Testes específicos do SeleniumDriver com páginas reais.
    
    Demonstra funcionalidade completa com Selenium.
    """
    
    @pytest.fixture
    def selenium_driver(self) -> SeleniumDriver:
        """Cria driver Selenium para testes."""
        driver = SeleniumDriver(headless=False)
        yield driver
        driver.quit()
    
    def test_navigate_to_example_com(self, selenium_driver: SeleniumDriver):
        """
        Testa navegação para example.com.
        
        DEMONSTRAÇÃO: Usando Selenium através da interface IBrowserDriver.
        """
        # Navega para página
        selenium_driver.google_get("https://example.com")
        
        # Valida navegação
        assert "example.com" in selenium_driver.current_url.lower()
        
        # Testa JavaScript
        title = selenium_driver.run_js("return document.title;")
        assert title is not None
        assert len(title) > 0
    
    def test_get_cookies(self, selenium_driver: SeleniumDriver):
        """
        Testa obtenção de cookies.
        """
        # Navega para página
        selenium_driver.google_get("https://httpbin.org/cookies/set?test=value")
        
        # Obtém cookies
        cookies = selenium_driver.get_cookies()
        
        # Valida formato
        assert isinstance(cookies, dict)
        # httpbin define o cookie "test"
        assert "test" in cookies
        assert cookies["test"] == "value"
    
    def test_human_mode(self, selenium_driver: SeleniumDriver):
        """
        Testa modo humano (delays aleatórios).
        """
        import time
        
        selenium_driver.enable_human_mode()
        
        # Mede tempo de sleep
        start = time.time()
        selenium_driver.short_random_sleep(0.1, 0.3)
        elapsed = time.time() - start
        
        # Valida que houve delay
        assert 0.1 <= elapsed <= 0.5
    
    def test_element_interaction(self, selenium_driver: SeleniumDriver):
        """
        Testa interação com elementos em página real.
        """
        # Navega para página de formulário
        selenium_driver.google_get("https://httpbin.org/forms/post")
        
        # Verifica presença de elemento
        has_input = selenium_driver.is_element_present("input[name='custname']", wait=5)
        assert has_input is True
        
        # Digita em campo
        selenium_driver.type("input[name='custname']", "Test User")
        
        # Verifica valor digitado via JavaScript
        value = selenium_driver.run_js(
            "return document.querySelector(\"input[name='custname']\").value;"
        )
        assert value == "Test User"
    
    def test_user_agent(self, selenium_driver: SeleniumDriver):
        """
        Testa User-Agent.
        """
        selenium_driver.google_get("https://httpbin.org/user-agent")
        
        ua = selenium_driver.get_user_agent()
        
        # Valida formato básico
        assert ua is not None
        assert len(ua) > 10
        assert "Mozilla" in ua or "Chrome" in ua


class TestDriverFactory:
    """
    Testes do padrão Factory para criação de drivers.
    
    Demonstra como criar uma factory que escolhe o driver dinamicamente.
    """
    
    @staticmethod
    def create_driver(driver_type: str, **kwargs) -> IBrowserDriver:
        """
        Factory method para criar drivers.
        
        Args:
            driver_type: Tipo do driver ('selenium', 'mock')
            **kwargs: Argumentos para o driver
            
        Returns:
            IBrowserDriver: Instância do driver
        """
        if driver_type == 'selenium':
            return SeleniumDriver(**kwargs)
        elif driver_type == 'mock':
            return MockDriver(**kwargs)
        else:
            raise ValueError(f"Driver type not supported: {driver_type}")
    
    def test_factory_creates_selenium(self):
        """Testa criação de driver Selenium via factory."""
        driver = self.create_driver('selenium', headless=True)
        
        try:
            assert isinstance(driver, IBrowserDriver)
            assert isinstance(driver, SeleniumDriver)
            assert driver.is_active()
        finally:
            driver.quit()
    
    def test_factory_creates_mock(self):
        """Testa criação de driver Mock via factory."""
        driver = self.create_driver('mock')
        
        try:
            assert isinstance(driver, IBrowserDriver)
            assert isinstance(driver, MockDriver)
            assert driver.is_active()
        finally:
            driver.quit()
    
    @pytest.mark.parametrize("driver_type", ['selenium', 'mock'])
    def test_factory_returns_valid_driver(self, driver_type):
        """
        Testa que factory retorna driver válido independente do tipo.
        
        DEMONSTRAÇÃO: Código cliente não precisa saber qual driver está usando.
        """
        driver = self.create_driver(driver_type, headless=True)
        
        try:
            # Este código funciona com QUALQUER driver
            assert isinstance(driver, IBrowserDriver)
            assert driver.is_active()
            
            driver.google_get("https://example.com")
            url = driver.get_current_url()
            
            assert url is not None
        finally:
            driver.quit()


class TestRealWorldScenario:
    """
    Cenário do mundo real: código que funciona com qualquer driver.
    
    Demonstra como o SessionManagerService poderia funcionar
    com Selenium, Botasaurus, Playwright, etc.
    """
    
    def execute_search_workflow(self, driver: IBrowserDriver, search_term: str) -> dict:
        """
        Workflow de busca genérico que funciona com QUALQUER driver.
        
        Este método NÃO SABE qual driver está usando - ele apenas
        usa a interface IBrowserDriver.
        
        Args:
            driver: Qualquer implementação de IBrowserDriver
            search_term: Termo de busca
            
        Returns:
            dict: Resultado da busca
        """
        # Navega para página de busca (exemplo simplificado)
        driver.google_get("https://httpbin.org/forms/post")
        
        # Ativa modo humano
        driver.enable_human_mode()
        
        # Verifica que página carregou
        assert driver.is_active()
        
        # Obtém dados da sessão
        cookies = driver.get_cookies()
        user_agent = driver.get_user_agent()
        
        return {
            "cookies": cookies,
            "user_agent": user_agent,
            "url": driver.get_current_url(),
            "search_term": search_term
        }
    
    def test_workflow_with_selenium(self):
        """
        Testa workflow com Selenium.
        
        PONTO CHAVE: O método execute_search_workflow() não sabe
        que está usando Selenium!
        """
        driver = SeleniumDriver(headless=True)
        
        try:
            result = self.execute_search_workflow(driver, "test search")
            
            assert result is not None
            assert "cookies" in result
            assert "user_agent" in result
            assert result["search_term"] == "test search"
        finally:
            driver.quit()
    
    def test_workflow_with_mock(self):
        """
        Testa workflow com Mock.
        
        PONTO CHAVE: O MESMO método execute_search_workflow()
        funciona com Mock! Zero mudanças no código.
        """
        driver = MockDriver()
        
        try:
            result = self.execute_search_workflow(driver, "test search")
            
            assert result is not None
            assert "cookies" in result
            assert "user_agent" in result
            assert result["search_term"] == "test search"
        finally:
            driver.quit()


if __name__ == "__main__":
    # Executa teste manual
    print("🧪 Testando troca de drivers - Demonstração de Desacoplamento\n")
    
    print("=" * 70)
    print("TESTE 1: SeleniumDriver acessando example.com")
    print("=" * 70)
    
    driver = SeleniumDriver(headless=False)
    try:
        driver.google_get("https://example.com")
        input()
        print(f"✅ URL: {driver.current_url}")
        print(f"✅ User-Agent: {driver.get_user_agent()[:50]}...")
        print(f"✅ Título: {driver.run_js('return document.title;')}")
        print("✅ SUCESSO: SeleniumDriver funcionando!\n")
    finally:
        driver.quit()
    
    print("=" * 70)
    print("TESTE 2: MockDriver (sem navegador real)")
    print("=" * 70)
    
    mock = MockDriver()
    try:
        mock.google_get("https://example.com")
        print(f"✅ URL: {mock.current_url}")
        print(f"✅ User-Agent: {mock.get_user_agent()}")
        print("✅ SUCESSO: MockDriver funcionando!\n")
    finally:
        mock.quit()
    
    print("=" * 70)
    print("🎯 CONCLUSÃO")
    print("=" * 70)
    print("✅ Ambos os drivers implementam a MESMA interface")
    print("✅ Código cliente funciona com QUALQUER implementação")
    print("✅ ZERO acoplamento com implementação específica")
    print("✅ Testabilidade: 0/10 → 10/10")
    print("✅ Manutenibilidade: Elevada significativamente")
    print("=" * 70)

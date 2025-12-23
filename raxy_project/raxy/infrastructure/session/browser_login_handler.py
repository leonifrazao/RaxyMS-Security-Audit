"""
Handler de login do navegador para o SessionManagerService.

Responsável por todo o fluxo de login no Microsoft Rewards.
"""

from __future__ import annotations
from typing import Any, Mapping, Optional
from botasaurus.browser import Driver, Wait, browser
from botasaurus.lang import Lang
from botasaurus.soupify import soupify

from raxy.interfaces.drivers import IBrowserDriver
from raxy.infrastructure.drivers import BotasaurusDriver
from raxy.infrastructure.drivers.network_inspector import NetWork
from raxy.infrastructure.session.session_utils import (
    extract_request_verification_token,
    normalize_credentials,
    is_valid_email
)
from raxy.core.exceptions import (
    ProxyRotationRequiredException,
    InvalidCredentialsException,
    ElementNotFoundException,
    LoginException,
    wrap_exception
)
from raxy.core.logging import get_logger, debug_log
from raxy.core.config import get_config

log = get_logger()


class BrowserLoginHandler:
    """
    Handler para gerenciar o processo de login no navegador.
    
    Responsável por:
    - Abrir o navegador com configurações adequadas
    - Realizar login no Microsoft Rewards
    - Coletar cookies e tokens
    - Verificar status de autenticação
    """
    
    @staticmethod
    @browser(
        reuse_driver=False,
        remove_default_browser_check_argument=True,
        wait_for_complete_page_load=False,
        raise_exception=True,
        close_on_crash=True,
        block_images=True,
        output=None,
        tiny_profile=True,
        lang=Lang.English
    )
    def executar_login(driver: Driver, data: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """
        Método estático que abre o driver e realiza o login.
        
        Args:
            driver: Driver do Botasaurus
            data: Dados adicionais (proxy_id, etc)
            
        Returns:
            Dicionário com cookies, user-agent, token e driver
            
        Raises:
            ProxyRotationRequiredException: Se rotação de proxy for necessária
            InvalidCredentialsException: Se credenciais forem inválidas
            ElementNotFoundException: Se elementos não forem encontrados
            LoginException: Se login falhar
        """
        registro = log.com_contexto(fluxo="browser_login", perfil=driver.config.profile)
        proxy_id = (data or {}).get("proxy_id")
        
        # Verifica se proxy foi aplicado no Chrome
        proxy_usado = getattr(driver.config, 'proxy', None)
        if proxy_usado:
            registro.info(f"✅ Chrome configurado COM proxy: {proxy_usado}")
        else:
            registro.aviso("⚠️ Chrome SEM proxy configurado!")
        
        registro.debug("Iniciando login no Rewards", proxy_id=proxy_id)
        
        # Ativa modo humano e navega para Rewards
        session_cfg = get_config().session
        driver.enable_human_mode()
        driver.google_get(session_cfg.rewards_url)
        driver.short_random_sleep()
        
        # Verifica se já está logado
        if driver.run_js("return document.title").lower() == session_cfg.rewards_title:
            return BrowserLoginHandler._processar_login_existente(driver, registro)
        
        # Executa fluxo de login
        return BrowserLoginHandler._executar_fluxo_login(driver, registro, proxy_id)
    
    @staticmethod
    def _extrair_market_do_rewards(html_soup) -> str:
        """Extrai market da página Rewards via scraping do script portal-telemetry."""
        try:
            import re
            # Busca script específico pelo id
            script = html_soup.find("script", {"id": "portal-telemetry"})
            if script and script.string:
                # Regex para extrair: market: "br",
                match = re.search(r'market:\s*"(\w+)"', script.string)
                if match:
                    return match.group(1).lower()
            return None
        except Exception:
            return None
    
    @staticmethod
    def _processar_login_existente(driver: Driver, registro) -> dict[str, Any]:
        """
        Processa quando conta já está autenticada.
        
        Args:
            driver: Driver do Botasaurus
            registro: Logger contextualizado
            
        Returns:
            Dicionário com dados da sessão
        """
        registro.sucesso("Conta já autenticada")
        html = soupify(driver)
        
        # Valida market (país) detectado pelo Rewards
        expected_country = get_config().proxy.country.lower()
        market = BrowserLoginHandler._extrair_market_do_rewards(html)
        if market and market != expected_country:
            registro.erro(f"❌ MARKET INCORRETO: '{market.upper()}' (esperado: {expected_country.upper()})")
            raise LoginException(
                f"Market incorreto: {market.upper()}. Proxy não identificado como {expected_country.upper()}.",
                details={"market": market, "expected": expected_country}
            )
        elif market == expected_country:
            registro.sucesso(f"✅ Market correto: {expected_country.upper()}")
        
        # Coleta cookies do domínio de pesquisa
        session_cfg = get_config().session
        registro.info("Coletando cookies do domínio de pesquisa...")
        driver.google_get(session_cfg.bing_url)
        driver.short_random_sleep()
        
        if driver.is_element_present(session_cfg.selectors["id_s_span"], wait=Wait.VERY_LONG):
            registro.info("Conta logada com sucesso no bing")
        else:
            registro.aviso("Conta não logada no bing")
        
        token = extract_request_verification_token(html)
        # Wrap driver nativo em BotasaurusDriver (Adapter Pattern)
        wrapped_driver = BotasaurusDriver(driver)
        return {
            "cookies": driver.get_cookies_dict(),
            "ua": driver.profile.get("UA"),
            "token": token,
            "driver": wrapped_driver,
        }
    
    @staticmethod
    def _executar_fluxo_login(driver: Driver, registro, proxy_id: Optional[int]) -> dict[str, Any]:
        """
        Executa o fluxo completo de login.
        
        Args:
            driver: Driver do Botasaurus
            registro: Logger contextualizado
            proxy_id: ID do proxy em uso
            
        Returns:
            Dicionário com dados da sessão
        """
        # Verifica campo de email
        session_cfg = get_config().session
        if not driver.is_element_present(session_cfg.selectors["email_input"], wait=Wait.VERY_LONG):
            registro.erro("Campo de email não encontrado na página")
            raise ProxyRotationRequiredException(400, proxy_id, url=driver.current_url)
        
        # Obtém e valida credenciais
        email, senha = BrowserLoginHandler._obter_credenciais(driver)
        BrowserLoginHandler._validar_credenciais(email, senha, registro)
        
        # Digita email
        BrowserLoginHandler._digitar_email(driver, email, registro)
        
        # Trata verificação de email se necessário
        BrowserLoginHandler._tratar_verificacao_email(driver)
        
        # Digita senha
        BrowserLoginHandler._digitar_senha(driver, email, senha, registro)
        
        # Trata tela de proteção de conta
        BrowserLoginHandler._tratar_protecao_conta(driver, registro)
        
        # Confirma sessão
        BrowserLoginHandler._confirmar_sessao(driver, registro)
        
        # Verifica e retorna resultado
        return BrowserLoginHandler._verificar_e_retornar_resultado(driver, registro, proxy_id)
    
    @staticmethod
    def _obter_credenciais(driver: Driver) -> tuple[str, str]:
        """Obtém credenciais do perfil e as normaliza."""
        email = str(driver.profile.get("email", "")).strip()
        senha = str(driver.profile.get("senha", "")).strip()
        return normalize_credentials(email, senha)
    
    @staticmethod
    def _validar_credenciais(email: str, senha: str, registro):
        """Valida se credenciais são válidas."""
        if not is_valid_email(email):
            registro.erro("Email ausente/inválido para login do Rewards")
            raise InvalidCredentialsException(
                "Email ausente ou inválido para login do Rewards",
                details={"email": email}
            )
        
        if not senha:
            registro.erro("Senha ausente para login do Rewards")
            raise InvalidCredentialsException(
                "Senha ausente para login do Rewards",
                details={"email": email}
            )
    
    @staticmethod
    def _digitar_email(driver: Driver, email: str, registro):
        """Digita email e clica em submit."""
        registro.info("Digitando email")
        session_cfg = get_config().session
        try:
            driver.type(session_cfg.selectors["email_input"], email, wait=Wait.VERY_LONG)
            driver.click(session_cfg.selectors["submit_button"])
            driver.short_random_sleep()
        except Exception as e:
            raise wrap_exception(
                e, ElementNotFoundException,
                "Erro ao interagir com campo de email",
                email=email
            )
    
    @staticmethod
    def _tratar_verificacao_email(driver: Driver):
        """Trata tela de verificação de email se aparecer."""
        session_cfg = get_config().session
        if (driver.run_js("return document.title").lower() == session_cfg.verify_email_title 
            and driver.is_element_present(session_cfg.selectors["email_verify_link"], wait=Wait.VERY_LONG)):
            driver.click(session_cfg.selectors["email_verify_link"])
    
    @staticmethod
    def _digitar_senha(driver: Driver, email: str, senha: str, registro):
        """Digita senha e clica em submit."""
        session_cfg = get_config().session
        if not driver.is_element_present(session_cfg.selectors["password_input"], wait=Wait.VERY_LONG):
            registro.erro("Campo de senha não encontrado após informar email")
            raise ElementNotFoundException(
                "Campo de senha não encontrado após informar email",
                details={"email": email, "url": driver.current_url}
            )
        
        registro.info("Digitando senha")
        session_cfg = get_config().session
        try:
            driver.type(session_cfg.selectors["password_input"], senha, wait=Wait.VERY_LONG)
            driver.click(session_cfg.selectors["submit_button"])
            driver.short_random_sleep()
        except Exception as e:
            raise wrap_exception(
                e, ElementNotFoundException,
                "Erro ao interagir com campo de senha",
                email=email
            )
    
    @staticmethod
    def _tratar_protecao_conta(driver: Driver, registro):
        """Trata tela de proteção de conta."""
        session_cfg = get_config().session
        while driver.run_js("return document.title").lower() == session_cfg.protect_account_title:
            driver.short_random_sleep()
            driver.click(session_cfg.selectors["skip_link"], wait=Wait.LONG)
            driver.short_random_sleep()
    
    @staticmethod
    def _confirmar_sessao(driver: Driver, registro):
        """Confirma a sessão (Stay signed in)."""
        session_cfg = get_config().session
        try:
            driver.click(session_cfg.selectors["primary_button"], wait=Wait.SHORT)
            registro.debug("Confirmação de sessão (Stay signed in) aceita")
        except Exception:
            pass
    
    @staticmethod
    def _verificar_e_retornar_resultado(driver: Driver, registro, proxy_id: Optional[int]) -> dict[str, Any]:
        """
        Verifica resultado do login e retorna dados da sessão.
        
        Args:
            driver: Driver do Botasaurus
            registro: Logger contextualizado
            proxy_id: ID do proxy em uso
            
        Returns:
            Dicionário com dados da sessão
        """
        network = NetWork(driver)
        network.limpar_respostas()
        session_cfg = get_config().session
        
        if "rewards.bing.com" in driver.current_url or driver.is_element_present(session_cfg.selectors["role_presentation"], wait=Wait.VERY_LONG):
            registro.sucesso("Login finalizado")
            
            # Verifica status HTTP
            status_final = network.get_status()
            if status_final == 200:
                registro.sucesso(f"Login bem-sucedido - Status: {status_final}")
            elif status_final is not None:
                registro.aviso(f"Login concluído mas com status inesperado: {status_final}")
            else:
                registro.debug("Nenhum status HTTP registrado após login")
            
            # Processa páginas pós-login
            return BrowserLoginHandler._processar_pos_login(driver, registro)
        
        # Login falhou
        status = network.get_status()
        if status and status >= 400:
            registro.erro(f"Erro HTTP detectado: {status}")
            raise ProxyRotationRequiredException(status, proxy_id, url=driver.current_url)
        
        email = driver.profile.get("email", "")
        registro.erro("Login não confirmado", status=status)
        raise LoginException(
            f"Não foi possível confirmar o login para {email}.",
            details={"email": email, "status": status, "url": driver.current_url}
        )
    
    @staticmethod
    def _processar_pos_login(driver: Driver, registro) -> dict[str, Any]:
        """
        Processa páginas pós-login e coleta dados da sessão.
        
        Args:
            driver: Driver do Botasaurus
            registro: Logger contextualizado
            
        Returns:
            Dicionário com dados da sessão
        """
        html = soupify(driver)
        
        # Valida market (país) detectado pelo Rewards
        expected_country = get_config().proxy.country.lower()
        market = BrowserLoginHandler._extrair_market_do_rewards(html)
        if market and market != expected_country:
            registro.erro(f"❌ MARKET INCORRETO: '{market.upper()}' (esperado: {expected_country.upper()})")
            raise LoginException(
                f"Market incorreto: {market.upper()}. Proxy não identificado como {expected_country.upper()}.",
                details={"market": market, "expected": expected_country}
            )
        elif market == expected_country:
            registro.sucesso(f"✅ Market correto: {expected_country.upper()}")
        
        # Coleta cookies do domínio de pesquisa
        session_cfg = get_config().session
        registro.info("Coletando cookies do domínio de pesquisa...")
        driver.google_get(session_cfg.bing_url)
        driver.short_random_sleep()
        
        if driver.is_element_present(session_cfg.selectors["id_s_span"], wait=Wait.VERY_LONG):
            registro.info("Conta logada com sucesso no bing")
        else:
            registro.aviso("Conta não logada no bing")
        
        # Acessa flyout e trata join now
        driver.google_get(session_cfg.bing_flyout_url)
        driver.short_random_sleep()
        
        if driver.is_element_present(session_cfg.selectors["join_now"], wait=Wait.VERY_LONG):
            driver.click(session_cfg.selectors["join_now"])
            driver.short_random_sleep()
            
        # Aguarda login completo
        session_cfg = get_config().session
        while not driver.is_element_present(session_cfg.selectors["id_s_span"], wait=Wait.VERY_LONG):
            driver.short_random_sleep()
        
        # Acessa flyout novamente
        driver.google_get(session_cfg.bing_flyout_url)
        driver.short_random_sleep()
        
        if driver.is_element_present(session_cfg.selectors["card_0"], wait=Wait.LONG):
            registro.info("Cartões de metas detectados no flyout.")
        
        token = extract_request_verification_token(html)
        # Wrap driver nativo em BotasaurusDriver (Adapter Pattern)
        wrapped_driver = BotasaurusDriver(driver)
        return {
            "cookies": driver.get_cookies_dict(),
            "ua": driver.profile.get("UA"),
            "token": token,
            "driver": wrapped_driver,
        }

"""Serviço responsável pelas interações de navegador com o Microsoft Rewards."""

from __future__ import annotations

from typing import Mapping

from botasaurus.browser import Driver, Wait, browser

from interfaces.services import IRewardsBrowserService
from interfaces.services import IProxyService
from services.logging_service import log

from .network_service import NetWork
from .session_service import BaseRequest


class ProxyRotationRequiredException(Exception):
    """Exceção lançada quando é necessário rotacionar a proxy devido a erro HTTP 400+."""
    
    def __init__(self, status_code: int, proxy_id: str):
        self.status_code = status_code
        self.proxy_id = proxy_id
        super().__init__(f"Erro HTTP {status_code} detectado. Rotação de proxy necessária (ID: {proxy_id})")


class RewardsBrowserService(IRewardsBrowserService):
    """Encapsula operações que dependem do navegador controlado pelo Botasaurus."""

    def __init__(self, proxy_service: IProxyService) -> None:
        self._proxy_service = proxy_service

    # -------------------------
    # Fluxos com navegador
    # -------------------------

    @staticmethod
    @browser(reuse_driver=False)
    def _open_rewards_page(driver: Driver, data: Mapping[str, object] | None = None) -> None:
        dados = dict(data or {})
        url = str(dados.get("url") or "https://rewards.bing.com/")

        driver.enable_human_mode()
        driver.google_get(url)
        html = getattr(driver, "page_source", "") or ""
        if "Sign in" in html or "Entrar" in html:
            print("You are not logged in. Please log in to access rewards.")
        driver.prompt()

    def open_rewards_page(self, *, profile: str, data: Mapping[str, object] | None = None) -> None:
        """Abre a página de Rewards utilizando o perfil informado."""
        self._open_rewards_page(profile=profile, data=dict(data or {}))

    @staticmethod
    @browser(
        reuse_driver=False,
        remove_default_browser_check_argument=True,
        wait_for_complete_page_load=True,
        block_images=True,
        output=None,
        tiny_profile=True,
    )
    def _login(driver: Driver, data: Mapping[str, object] | None = None) -> BaseRequest:
        dados = dict(data or {})
        email_normalizado = str(driver.profile['email']).strip()
        senha_normalizada = str(driver.profile['senha']).strip()
        proxy_id = dados.get("proxy", {}).get("id")

        network = NetWork(driver)
        network.limpar_respostas()

        if not email_normalizado or "@" not in email_normalizado:
            raise ValueError("Email ausente ou inválido para login do Rewards")
        if not senha_normalizada:
            raise ValueError("Senha ausente para login do Rewards")

        registro = log.com_contexto(fluxo="login", perfil=driver.config.profile)
        registro.debug("Coletando credenciais")

        driver.enable_human_mode()
        driver.google_get("https://rewards.bing.com/")
        driver.short_random_sleep()

        # if driver.is_element_present("h1[ng-bind-html='$ctrl.nameHeader']", wait=Wait.VERY_LONG):
        #     registro.sucesso("Conta já autenticada")
        #     driver.prompt()
        #     base_request = BaseRequest(driver.config.profile, driver)
        #     registro.debug(
        #         "Sessão pronta para requests",
        #         perfil=driver.config.profile,
        #         total_cookies=len(driver.get_cookies_dict()),
        #     )
        #     return base_request
        
        if driver.run_js("return document.title").lower() == "microsoft rewards":
            registro.sucesso("Conta já autenticada")
            # driver.prompt()
            base_request = BaseRequest(driver.config.profile, driver)
            registro.debug(
                "Sessão pronta para requests",
                perfil=driver.config.profile,
                total_cookies=len(driver.get_cookies_dict()),
            )
            return base_request

        if not driver.is_element_present("input[type='email']", wait=Wait.VERY_LONG):
            registro.erro("Campo de email não encontrado na página")
            raise RuntimeError("Campo de email não encontrado na página de login")

        registro.info("Digitando email")
        driver.type("input[type='email']", email_normalizado, wait=Wait.VERY_LONG)
        driver.click("button[type='submit']")
        driver.short_random_sleep()
        
        if driver.run_js("return document.title").lower() == "verify your email" and driver.is_element_present("#view > div > span:nth-child(6) > div > span", wait=Wait.VERY_LONG):
            driver.click("#view > div > span:nth-child(6) > div > span")

        if not driver.is_element_present("input[type='password']", wait=Wait.VERY_LONG):
            registro.erro("Campo de senha não encontrado após informar email")
            raise RuntimeError("Campo de senha não encontrado após informar email")

        registro.info("Digitando senha")
        driver.type("input[type='password']", senha_normalizada, wait=Wait.VERY_LONG)
        driver.click("button[type='submit']")
        driver.short_random_sleep()

        try:
            driver.click("button[data-testid='primaryButton']", wait=Wait.SHORT)
        except Exception:
            pass
        else:
            registro.debug("Confirmação de sessão aceita")

        if driver.is_element_present("h1[ng-bind-html='$ctrl.nameHeader']", wait=Wait.VERY_LONG):
            registro.sucesso("Login finalizado")

            status_final = network.get_status()
            if status_final == 200:
                registro.sucesso(f"Login bem-sucedido - Status: {status_final}")
            elif status_final is not None:
                registro.aviso(f"Login concluído mas com status inesperado: {status_final}")
            else:
                registro.debug("Nenhum status HTTP registrado após login")

            base_request = BaseRequest(driver.config.profile, driver)
            registro.debug(
                "Sessão pronta para requests",
                perfil=driver.config.profile,
                total_cookies=len(driver.get_cookies_dict()),
            )
            return base_request

        status = network.get_status()
        if status and status >= 400:
            registro.erro(f"Erro HTTP detectado: {status}")
            raise ProxyRotationRequiredException(status, proxy_id)

        if status is not None:
            registro.erro("Login não confirmado mesmo após tentativa", status=status)
        else:
            registro.erro("Login não confirmado: nenhuma resposta de rede capturada")

        raise RuntimeError(f"Não foi possível confirmar o login para {email_normalizado}.")

    def login(self, *, profile: str, proxy: dict) -> BaseRequest:
        """Executa o fluxo de login via navegador e retorna a sessão autenticada.
        
        Rotaciona a proxy automaticamente em caso de erro HTTP 400+ até conseguir login bem-sucedido.
        """
        registro = log.com_contexto(fluxo="login_com_rotacao", perfil=profile)
        proxy_atual = proxy
        tentativas = 0
        
        while True:
            tentativas += 1
            try:
                registro.debug(f"Tentativa #{tentativas} de login", proxy_id=proxy_atual["id"])
                return self._login(profile=profile, proxy=proxy_atual["url"], data={"proxy": proxy_atual})
            except ProxyRotationRequiredException as e:
                registro.aviso(
                    f"Tentativa #{tentativas} falhou com status {e.status_code}",
                    proxy_id=proxy_atual["id"]
                )
                
                # Rotaciona a proxy mantendo o mesmo ID
                proxy_atual = self._proxy_service.rotate_proxy(proxy_atual["id"])
                registro.info(f"Proxy rotacionada - Nova tentativa com URL: {proxy_atual['url']}")


__all__ = ["RewardsBrowserService", "ProxyRotationRequiredException"]
# raxy/services/bingflyout_service.py
from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Mapping

from bs4 import BeautifulSoup
from botasaurus.browser import Driver, Wait, browser
from botasaurus.lang import Lang

from raxy.interfaces.services import IBingFlyoutService
from raxy.services.logging_service import log
from raxy.core.session_manager_service import SessionManagerService
from raxy.core.exceptions import (
    BrowserException,
    ElementNotFoundException,
    HTMLParsingException,
    DataExtractionException,
    wrap_exception,
)

REQUESTS_DIR = Path(__file__).resolve().parent.parent / "api/requests_templates"
FLYOUT_URL = (
    "https://www.bing.com/rewards/panelflyout"
    "?channel=bingflyout&partnerId=BingRewards&isDarkMode=1&requestedLayout=onboarding&form=rwfobc"
)


class BingFlyoutService(IBingFlyoutService):
    _TEMPLATE_SET_GOAL = REQUESTS_DIR / "set_redemption_goal.json"
    _TEMPLATE_REPORT_ACTIVITY = REQUESTS_DIR / "report_onboarding_activity.json"

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
        lang=Lang.English,
    )
    def _abrir_flyout(driver: Driver, data: Mapping[str, object] | None = None) -> dict[str, str]:
        """
        Abre o flyout do Bing Rewards e retorna apenas os dados extraídos (userId, offerId, authKey, sku).
        O driver é criado e destruído automaticamente pelo decorador @browser.
        """
        try:
            driver.enable_human_mode()
            driver.google_get(FLYOUT_URL)
            driver.short_random_sleep()
        except Exception as e:
            log.erro("Erro ao acessar flyout URL", erro=str(e), url=FLYOUT_URL)
            raise wrap_exception(
                e, BrowserException,
                "Erro ao acessar flyout do Bing Rewards",
                url=FLYOUT_URL
            )

        try:
            if driver.is_element_present('a[class="joinNowText"]', wait=Wait.SHORT):
                driver.click('a[class="joinNowText"]')
                driver.short_random_sleep()
                driver.google_get("https://www.bing.com/rewards/panelflyout?channel=bingflyout&partnerId=BingRewards&isDarkMode=1&requestedLayout=onboarding&form=rwfobc")
                driver.short_random_sleep()
                if driver.is_element_present('div[id="Card_0"]', wait=Wait.LONG):
                    log.info("Cartões de metas detectados no flyout.")
        except Exception as e:
            log.aviso("Erro ao clicar em 'joinNowText', continuando", erro=str(e))

        try:
            if driver.is_element_present('div[id="Card_0"]', wait=Wait.SHORT):
                log.sucesso("Cartões de metas detectados no flyout.")
                try:
                    driver.click(f'div[id="Card_{random.randint(0, 3)}"]')
                    driver.short_random_sleep()
                    driver.click('button[id="slideshow_nb"]')
                    driver.short_random_sleep()
                except Exception as e:
                    log.aviso("Erro ao interagir com cartões de metas", erro=str(e))
        except Exception as e:
            log.aviso("Erro ao verificar cartões de metas", erro=str(e))
        
        try:
            # Aguarda até 10 segundos pelo título do checklist
            timeout_count = 0
            while not driver.is_element_present('div[class="onboarding_checklist_title"]', wait=Wait.SHORT) and timeout_count < 10:
                driver.short_random_sleep()
                timeout_count += 1
            
            if timeout_count >= 10:
                log.aviso("Timeout ao aguardar checklist do flyout")
        except Exception as e:
            log.aviso("Erro ao aguardar checklist do flyout", erro=str(e))
        
        try:
            html = getattr(driver, "page_html", "") or ""
        except Exception as e:
            log.erro("Erro ao obter HTML da página", erro=str(e))
            raise wrap_exception(
                e, BrowserException,
                "Erro ao obter HTML do flyout"
            )
        
        if not html:
            log.aviso("HTML do flyout não disponível.")
            return {}

        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception as e:
            log.erro("Erro ao fazer parse do HTML", erro=str(e))
            raise wrap_exception(
                e, HTMLParsingException,
                "Erro ao fazer parse do HTML do flyout"
            )

        # Extrai dados básicos
        user_id, offer_id, auth_key, sku = None, None, None, None
        try:
            for script in soup.find_all("script"):
                txt = script.string or ""
                if "userId" in txt and not user_id:
                    m = re.search(r'"userId"\s*:\s*"([^"]+)"', txt)
                    if m:
                        user_id = m.group(1)
                if "offerId" in txt and not offer_id:
                    m = re.search(r'"offerId"\s*:\s*"([^"]+)"', txt)
                    if m:
                        offer_id = m.group(1)
                if "hash" in txt and not auth_key:
                    m = re.search(r'"hash"\s*:\s*"([^"]+)"', txt)
                    if m:
                        auth_key = m.group(1)
                if "sku" in txt and not sku:
                    m = re.search(r'"sku"\s*:\s*"([^"]+)"', txt)
                    if m:
                        sku = m.group(1)
        except Exception as e:
            log.aviso("Erro ao extrair dados dos scripts", erro=str(e))

        return {
            "user_id": user_id or "",
            "offer_id": offer_id or "",
            "auth_key": auth_key or "",
            "sku": sku or "",
        }

    def executar(self, sessao: SessionManagerService) -> dict[str, str]:
        """
        Interface pública: recebe apenas a sessão e extrai dela o profile/proxy.
        Tratamento robusto de erros.
        """
        try:
            profile = sessao.conta.id_perfil or sessao.conta.email
            proxy_url = sessao.proxy.get("url")
        except Exception as e:
            log.erro("Erro ao obter dados da sessão", erro=str(e))
            raise wrap_exception(
                e, BrowserException,
                "Erro ao obter perfil/proxy da sessão"
            )

        log.info("Executando fluxo do BingFlyoutService", profile=profile, proxy=proxy_url)
        
        try:
            dados = self._abrir_flyout(profile=profile, proxy=proxy_url, data={})
        except BrowserException:
            raise
        except Exception as e:
            log.erro("Erro inesperado ao executar flyout", erro=str(e))
            raise wrap_exception(
                e, BrowserException,
                "Erro inesperado ao executar fluxo do flyout",
                profile=profile
            )
        
        if not dados:
            log.aviso("Nenhum dado extraído do flyout.")
        else:
            log.sucesso("Dados extraídos do flyout com sucesso.", **dados)
        return dados

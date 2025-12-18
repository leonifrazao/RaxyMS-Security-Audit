"""
Serviço para gerenciar o flyout do Bing Rewards.

Implementa o fluxo de onboarding do flyout usando automação do browser.
"""

from __future__ import annotations

import random
import re
from typing import Dict, Any

from bs4 import BeautifulSoup
from botasaurus.browser import Driver, browser
from botasaurus.lang import Lang

from raxy.core.exceptions import BrowserException, wrap_exception
from raxy.infrastructure.logging import get_logger
from raxy.infrastructure.config.config import get_config


# Configuração do browser
BROWSER_OPTIONS = {
    'reuse_driver': False,
    'wait_for_complete_page_load': False,
    'raise_exception': True,
    'close_on_crash': True,
    'block_images': True,
    'output': None,
    'tiny_profile': True,
    'lang': Lang.English,
}


def extrair_dados_flyout(html: str) -> Dict[str, str]:
    """Extrai dados do HTML do flyout."""
    try:
        soup = BeautifulSoup(html, "lxml")
    except:
        return {}
    
    dados = {"user_id": "", "offer_id": "", "auth_key": "", "sku": ""}
    
    for script in soup.find_all("script"):
        txt = script.string or ""
        
        if "userId" in txt and not dados["user_id"]:
            m = re.search(r'"userId"\s*:\s*"([^"]+)"', txt)
            if m:
                dados["user_id"] = m.group(1)
        
        if "offerId" in txt and not dados["offer_id"]:
            m = re.search(r'"offerId"\s*:\s*"([^"]+)"', txt)
            if m:
                dados["offer_id"] = m.group(1)
        
        if "hash" in txt and not dados["auth_key"]:
            m = re.search(r'"hash"\s*:\s*"([^"]+)"', txt)
            if m:
                dados["auth_key"] = m.group(1)
        
        if "sku" in txt and not dados["sku"]:
            m = re.search(r'"sku"\s*:\s*"([^"]+)"', txt)
            if m:
                dados["sku"] = m.group(1)
    
    return dados


@browser(**BROWSER_OPTIONS)
def _abrir_flyout(driver: Driver, data: dict = None) -> Dict[str, Any]:
    """
    Abre o flyout e extrai dados.
    
    O driver é criado automaticamente pelo decorador @browser.
    """
    try:
        driver.enable_human_mode()
        driver.google_get(get_config().session.bing_flyout_url)
        driver.short_random_sleep()
    except Exception as e:
        raise wrap_exception(e, BrowserException, "Erro ao acessar flyout")

    # Clica "Join Now" se presente
    try:
        if driver.is_element_present('a[class="joinNowText"]', wait=3):
            driver.click('a[class="joinNowText"]')
            driver.short_random_sleep()
            driver.google_get(get_config().session.bing_flyout_url)
            driver.short_random_sleep()
    except:
        pass
    
    # Detecta conta bugada (DailySet após Join Now)
    try:
        if driver.is_element_present('div[aria-labelledby="DailySet"]', wait=3):
            return {"conta_bugada": True, "erro": "DailySet presente"}
    except:
        pass

    # Interage com cartões de metas
    try:
        if driver.is_element_present('div[id="Card_0"]', wait=3):
            driver.click(f'div[id="Card_{random.randint(0, 3)}"]')
            driver.short_random_sleep()
            try:
                driver.click('button[id="slideshow_nb"]')
                driver.short_random_sleep()
            except:
                pass
    except:
        pass
    
    # Aguarda checklist
    try:
        for _ in range(10):
            if driver.is_element_present('#daily-streaks > div.threeOffers_header', wait=2):
                break
            driver.short_random_sleep()
    except:
        pass
    
    # Extrai dados do HTML
    html = getattr(driver, "page_html", "") or ""
    dados = extrair_dados_flyout(html) if html else {}
    dados["conta_bugada"] = False
    
    return dados


class BingFlyoutService:
    """
    Serviço para executar o flyout do Bing Rewards.
    
    Uso:
        flyout = BingFlyoutService()
        resultado = flyout.executar(sessao)
    """
    
    def __init__(self, logger=None):
        self.logger = logger or get_logger()
    
    def executar(self, sessao: Any) -> Dict[str, Any]:
        """
        Executa o fluxo do flyout.
        
        Args:
            sessao: SessionManagerService com conta e proxy
            
        Returns:
            Dict com dados extraídos ou erro
        """
        profile = sessao.conta.id_perfil or sessao.conta.email
        proxy_url = sessao.proxy.url if hasattr(sessao, 'proxy') and sessao.proxy and hasattr(sessao.proxy, 'url') else None
        
        self.logger.info(f"Executando flyout para {profile}")
        
        dados = _abrir_flyout(profile=profile, proxy=proxy_url, data={})
        
        if dados.get("conta_bugada"):
            self.logger.erro("Conta com bug detectada", conta=profile)
            # Pode levantar exceção se considerar bug como falha
            # raise Exception("Conta com bug detectada")
        else:
            self.logger.sucesso(f"Flyout concluído para {profile}")
            
        return dados

"""
Serviço refatorado para gerenciar o flyout do Bing Rewards.

Implementa o fluxo de onboarding do flyout com tratamento robusto de erros,
seguindo padrões SOLID e arquitetura limpa.
"""

from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Dict, Mapping, Optional, Any
from raxy.domain.flyout import FlyoutResult
import time

from bs4 import BeautifulSoup
from botasaurus.browser import Driver, Wait, browser
from botasaurus.lang import Lang

from raxy.interfaces.services import IBingFlyoutService, ILoggingService, ISessionManager
from raxy.core.exceptions import (
    BrowserException,
    ElementNotFoundException,
    HTMLParsingException,
    DataExtractionException,
    wrap_exception,
)
from raxy.core.config import get_config
from raxy.core.logging import debug_log, get_logger
from .base_service import BaseService


BROWSER_OPTIONS = {
    'reuse_driver': False,
    'remove_default_browser_check_argument': True,
    'wait_for_complete_page_load': False,
    'raise_exception': True,
    'close_on_crash': True,
    'block_images': True,
    'output': None,
    'tiny_profile': True,
    'lang': Lang.English,
}


class FlyoutDataExtractor:
    """Extrator de dados do HTML do flyout."""
    
    @staticmethod
    def extract(html: str) -> Dict[str, str]:
        """
        Extrai dados relevantes do HTML do flyout.
        
        Args:
            html: HTML da página do flyout
            
        Returns:
            FlyoutResult: Dados extraídos (user_id, offer_id, auth_key, sku)
            
        Raises:
            HTMLParsingException: Se erro ao fazer parse do HTML
        """
        logger = get_logger()
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception as e:
            logger.erro("Erro ao fazer parse do HTML com BeautifulSoup", exception=e)
            raise wrap_exception(
                e, HTMLParsingException,
                "Erro ao fazer parse do HTML do flyout"
            )
        
        # Extrai dados dos scripts
        user_id, offer_id, auth_key, sku = None, None, None, None
        
        try:
            scripts = soup.find_all("script")
            logger.debug(f"Analisando {len(scripts)} scripts para extração de dados")
            
            for script in scripts:
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
            logger.aviso("Erro durante iteração dos scripts para extração", exception=e)
            pass
        
        logger.debug(
            "Extração do flyout concluída", 
            extra={
                "found_user": bool(user_id), 
                "found_offer": bool(offer_id), 
                "found_auth": bool(auth_key)
            }
        )
        
        return FlyoutResult(
            user_id=user_id or "",
            offer_id=offer_id or "",
            auth_key=auth_key or "",
            sku=sku or "",
        )


class BingFlyoutService(BaseService, IBingFlyoutService):
    """
    Serviço para gerenciar o flyout do Bing Rewards.
    
    Implementa o fluxo de onboarding usando automação do browser
    com o decorador @browser do botasaurus.
    """
    
    def __init__(self, logger: Optional[ILoggingService] = None):
        """
        Inicializa o serviço.
        
        Args:
            logger: Serviço de logging (opcional)
        """
        super().__init__(logger)
        self.extractor = FlyoutDataExtractor()

    @staticmethod
    @browser(**BROWSER_OPTIONS)
    def _abrir_flyout(driver: Driver, data: Mapping[str, object] | None = None) -> Optional[FlyoutResult]:
        """
        Abre o flyout do Bing Rewards e retorna dados extraídos.
        
        O driver é criado e destruído automaticamente pelo decorador @browser.
        
        Args:
            driver: Driver do browser (injetado pelo decorador)
            data: Dados adicionais (profile, proxy, etc)
            
        Returns:
            Dict[str, str]: Dados extraídos do flyout
        """
        flyout_url = get_config().session.bing_flyout_url
        try:
            driver.enable_human_mode()
            driver.google_get(flyout_url)
            driver.short_random_sleep()
        except Exception as e:
            raise wrap_exception(
                e, BrowserException,
                "Erro ao acessar flyout do Bing Rewards",
                url=flyout_url
            )

        logger = get_logger()
        logger.debug("Flyout acessado, verificando elementos...")

        # Trata botão "Join Now" se presente
        try:
            if driver.is_element_present('a[class="joinNowText"]', wait=get_config().bingflyout.timeout_short):
                logger.info("Botão 'Join Now' encontrado, clicando...")
                driver.click('a[class="joinNowText"]')
                driver.short_random_sleep()
                driver.google_get(flyout_url)
                driver.short_random_sleep()
        except Exception:
            pass  # Ignora se não encontrar
        
        # VALIDAÇÃO CRÍTICA: Detectar conta bugada APÓS Join Now
        # A presença do elemento DailySet após Join Now indica conta bugada
        try:
            elemento_presente = driver.is_element_present(
                'div[aria-labelledby="DailySet"]',
                wait=get_config().bingflyout.timeout_short
            )
            
            if elemento_presente:
                # CONTA BUGADA DETECTADA - INTERROMPE O FLUXO IMEDIATAMENTE
                return FlyoutResult(
                    user_id="",
                    offer_id="",
                    auth_key="",
                    sku="",
                    conta_bugada=True,
                    bug_detalhes="Elemento DailySet presente após Join Now"
                )
        
        except Exception as e:
            # Erro na detecção não deve quebrar o fluxo
            pass

        # Interage com cartões de metas se presentes
        try:
            if driver.is_element_present('div[id="Card_0"]', wait=get_config().bingflyout.timeout_short):
                driver.click(f'div[id="Card_{random.randint(0, 3)}"]')
                driver.short_random_sleep()
                try:
                    driver.click('button[id="slideshow_nb"]')
                    driver.short_random_sleep()
                except Exception:
                    pass  # Ignora se não encontrar botão
        except Exception:
            pass  # Ignora se não encontrar cartões
        
        # Aguarda checklist aparecer
        try:
            timeout_count = 0
            cfg = get_config().bingflyout
            while not driver.is_element_present('div[class="onboarding_checklist_title"]', wait=cfg.timeout_short) and timeout_count < cfg.max_wait_iterations:
                driver.short_random_sleep()
                timeout_count += 1
        except Exception:
            pass  # Ignora timeout
        
        # Obtém e extrai dados do HTML
        try:
            html = getattr(driver, "page_html", "") or ""
        except Exception as e:
            raise wrap_exception(
                e, BrowserException,
                "Erro ao obter HTML do flyout"
            )
        
        if not html:
            return FlyoutResult(
                user_id="",
                offer_id="",
                auth_key="",
                sku="",
                conta_bugada=False,
                bug_detalhes="Conta normal"
            )
        
        # Extrai dados usando o extrator
        dados_extraidos = FlyoutDataExtractor.extract(html)
        
        # Adiciona flag de bug aos dados extraídos (se chegou aqui, não tem bug)
        # O objeto é imutável frozen, então retornamos como está pois o default é False
        # Se precisássemos alterar, teríamos que criar novo objeto.
        # Mas o extrator retorna defaults que são ok.
        
        return dados_extraidos

    @debug_log(log_args=False, log_result=False, log_duration=True)
    def executar(self, sessao: ISessionManager) -> Optional[FlyoutResult]:
        """
        Executa o fluxo do flyout.
        
        Args:
            sessao: Sessão do usuário
            
        Returns:
            Optional[FlyoutResult]: Dados extraídos do flyout
            
        Raises:
            BrowserException: Se erro durante execução
        """
        # Valida entrada
        self.validate_input(sessao=sessao)
        
        # Extrai informações da sessão
        try:
            profile = sessao.conta.id_perfil or sessao.conta.email
            proxy_url = sessao.proxy.get("url")
        except Exception as e:
            self.handle_error(e, {"context": "extração de dados da sessão"})
        
        self.logger.info(
            "Executando fluxo do BingFlyout",
            profile=profile,
            proxy=proxy_url
        )
        
        try:
            with self.logger.etapa("BingFlyout"):
                # Executa método decorado com @browser
                dados = self._abrir_flyout(profile=profile, proxy=proxy_url, data={})
                
                if not dados:
                    self.logger.aviso("Nenhum dado extraído do flyout")
                    return dados
                
                # Verificação crítica: conta bugada
                if dados.conta_bugada:
                    self.logger.erro(
                        "Conta com bug detectada - interrompendo flyout",
                        detalhes=dados.bug_detalhes or "Elemento DailySet presente",
                        conta=profile
                    )
                    
                    
                    return dados
                
                # Conta normal - continua logging
                self.logger.info(
                    "Validação de bug: conta normal",
                    detalhes=dados.bug_detalhes or "Sem bugs detectados"
                )
                self.logger.sucesso("Dados extraídos do flyout com sucesso")
                
                return dados
                
        except BrowserException as e:
            raise
        except Exception as e:
            self.handle_error(e, {
                "context": "execução do flyout",
                "profile": profile
            })

# raxy_project/raxy/services/bingflyout_service.py

from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from raxy.interfaces.services import IBingFlyoutService, ILoggingService
from raxy.core.session_service import SessaoSolicitacoes

from botasaurus.browser import Driver, Wait, browser
from botasaurus.lang import Lang
from botasaurus.soupify import soupify 
from raxy.services.logging_service import log
import random

# Caminho para os templates de requisição
REQUESTS_DIR = Path(__file__).resolve().parent.parent / "api/requests_templates"

# Endpoints da API
FLYOUT_URL = "https://www.bing.com/rewards/panelflyout?channel=bingflyout&partnerId=BingRewards&isDarkMode=1&requestedLayout=onboarding&form=rwfobc"


class BingFlyoutService(IBingFlyoutService):
    """
    Implementação do serviço que interage com o painel flyout para ações de onboarding,
    utilizando apenas requisições HTTP diretas.
    """

    _TEMPLATE_SET_GOAL = REQUESTS_DIR / "set_redemption_goal.json"
    _TEMPLATE_REPORT_ACTIVITY = REQUESTS_DIR / "report_onboarding_activity.json"
    
    @browser(reuse_driver=False, lang=Lang.English, tiny_profile=True, output=None)
    def _abrir_flyout(driver: Driver, data: dict = None) -> None:
        driver.enable_human_mode()
        driver.google_get(FLYOUT_URL)
        
        if driver.is_element_present('a[class="joinNowText"]', wait=Wait.SHORT):
            driver.click('a[class="joinNowText"]')
            driver.short_random_sleep()
            
        # div[class="flyout_onboarding_checklist"]
        if driver.is_element_present('div[class="checklist_divider_text"]', wait=Wait.SHORT):
            log.sucesso("Flyout  aberto com sucesso.")
            if driver.is_element_present('div[class="flyout_onboarding_checklist"]', wait=Wait.SHORT):
                log.info("Flyout de onboarding detectado.")
            else:
                log.aviso("Flyout aberto, mas sem checklist de onboarding.")
                return
        else:
            log.aviso("Onboarding ainda não aparece, tentando pegar goal!")
        
        if driver.is_element_present('div[id="Card_0"]', wait=Wait.SHORT):
            log.sucesso("Cartões de metas detectados no flyout.")
            driver.click(f'div[id="Card_{random.randint(0, 3)}"]')
            driver.click('#slideshow_nb > span:nth-child(1)')
        else:
            log.erro("Nenhum cartão de metas detectado no flyout.")
            
        return
        
    def abrir_flyout(self, *, profile: str, proxy: dict) -> None:
        """Abre o painel flyout de onboarding utilizando o perfil informado."""
        self._abrir_flyout(profile=profile, proxy=proxy["url"],  data={})


    def _extrair_dados_onboarding(self, sessao: SessaoSolicitacoes) -> dict[str, Any] | None:
        """
        Acessa a página do flyout com uma requisição headless para obter o HTML
        e extrai os dados dinâmicos necessários.
        """
        # Cria uma requisição GET simples para o flyout usando o executor da sessão
        scoped_logger = self._logger.com_contexto(perfil=sessao.perfil, acao="extrair_dados_onboarding")
        flyout_request_template = {
            "method": "GET",
            "url": FLYOUT_URL,
            "headers": {"Accept": "text/html,application/xhtml+xml"},
        }
        resposta_flyout = sessao.base_request.executar(flyout_request_template)
        html_content = getattr(resposta_flyout, "text", "")
        
        if not html_content:
            raise RuntimeError("Não foi possível obter o conteúdo HTML da página do flyout.")

        soup = BeautifulSoup(html_content, 'lxml')
        
        all_scripts = soup.find_all('script')
        flyout_result_str = None
        
        for script in all_scripts:
            if script.string and '"flyoutResult":' in script.string:
                match = re.search(r'"flyoutResult":\s*({.*?}),\s*"channel":', script.string, re.DOTALL)
                if match:
                    flyout_result_str = match.group(1)
                    break
        
        if not flyout_result_str:
            raise ValueError("Não foi possível encontrar o JSON 'flyoutResult' no HTML do flyout.")

        flyout_result_data = json.loads(flyout_result_str)
        
        try:
            # A chave 'userId' agora está no nível superior do 'flyoutViewModel',
            # que contém o 'flyoutResult'. Vamos extrair o viewModel completo.
            view_model_match = re.search(r'window\.flyoutViewModel\s*=\s*({.*?});', html_content, re.DOTALL)
            if not view_model_match:
                raise ValueError("Não foi possível encontrar o JSON 'flyoutViewModel' no HTML do flyout.")
            
            view_model_data = json.loads(view_model_match.group(1))
            onboarding_promo = flyout_result_data.get("onboardingPromotion")
            
            # Adiciona uma verificação para o caso de onboarding_promo ser None
            if onboarding_promo is None or not flyout_result_data.get("userStatus"):
                # Não é um erro, apenas a promoção não está ativa. Retorna None.
                return None

            skus_disponiveis = [item["sku"] for item in onboarding_promo.get("redemptionGoalItems", []) if item]
            
            return {
                "user_id": view_model_data["userId"],
                "offer_id": onboarding_promo["offerId"],
                "auth_key": onboarding_promo["hash"],
                "skus_disponiveis": skus_disponiveis,
            }
        except KeyError as e:
            raise ValueError(f"Estrutura do JSON 'flyoutResult' inesperada. Chave ausente: {e}")

    def _executar_report_activity(self, sessao: SessaoSolicitacoes, dados: dict[str, Any]) -> None:
        """Executa a requisição para reportar a atividade de onboarding."""
        with open(self._TEMPLATE_REPORT_ACTIVITY, "r", encoding="utf-8") as f:
            template = json.load(f)
        
        # Modifica o payload JSON diretamente no dicionário do template
        payload = template["json"]
        payload["offerid"] = dados["offer_id"]
        payload["authkey"] = dados["auth_key"]
        payload["userid"] = dados["user_id"]
        
        # Monta os argumentos da requisição com o template modificado e depois envia
        args = sessao.base_request._montar(template, bypass_request_token=False)
        resposta = sessao.base_request._enviar(args)
        
        if not getattr(resposta, "ok", False):
            raise RuntimeError(f"Falha ao reportar atividade. Status: {getattr(resposta, 'status_code', 'N/A')}")
            
        self._logger.sucesso("Atividade de onboarding reportada com sucesso!", resposta=resposta.json())
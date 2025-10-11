# raxy_project/raxy/services/bingflyout_service.py

from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from raxy.interfaces.services import IBingFlyoutService, ILoggingService
from raxy.core.session_service import SessaoSolicitacoes

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

    def __init__(self, logger: ILoggingService):
        self._logger = logger

    def set_goal(self, sessao: SessaoSolicitacoes, sku: str) -> bool:
        """
        Executa o fluxo completo para definir uma meta de resgate e coletar os pontos de bônus.
        """
        scoped_logger = self._logger.com_contexto(perfil=sessao.perfil, acao="set_goal")
        
        try:
            with scoped_logger.etapa("Definir meta de resgate via API", sku=sku):
                # 1. Extrair dados dinâmicos da página do flyout via request headless
                scoped_logger.info("Extraindo dados de onboarding da página do flyout...")
                dados_onboarding = self._extrair_dados_onboarding(sessao) # Pode retornar None

                if not dados_onboarding:
                    scoped_logger.aviso("Promoção de onboarding não encontrada ou indisponível. Ignorando definição de meta.")
                    # Retorna True porque a ausência da promoção não é um erro de execução.
                    return True
                
                if sku not in dados_onboarding["skus_disponiveis"]:
                    scoped_logger.aviso(
                        "SKU fornecido não está na lista de metas disponíveis.",
                        sku_fornecido=sku,
                        skus_validos=dados_onboarding["skus_disponiveis"]
                    )

                # 2. Enviar a requisição para definir a meta
                scoped_logger.info("Enviando requisição para definir a meta...")
                self._executar_set_goal(sessao, sku)

                # 3. Enviar a requisição para reportar a atividade e ganhar os pontos
                scoped_logger.info("Reportando atividade para coletar bônus de 50 pontos...")
                self._executar_report_activity(sessao, dados_onboarding)
                
                return True

        except Exception as e:
            scoped_logger.erro("Falha no processo de definir meta.", erro=str(e))
            return False

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

    def _executar_set_goal(self, sessao: SessaoSolicitacoes, sku: str) -> None:
        """Executa a requisição para definir a meta usando o template."""
        with open(self._TEMPLATE_SET_GOAL, "r", encoding="utf-8") as f:
            template = json.load(f)
        
        # Formata a string 'data' com o SKU fornecido
        template["data"] = template["data"].format(sku=sku)

        # Monta e envia a requisição
        args = sessao.base_request._montar(template, bypass_request_token=False)
        resposta = sessao.base_request._enviar(args)
        
        if not getattr(resposta, "ok", False):
            raise RuntimeError(f"Falha ao definir meta. Status: {getattr(resposta, 'status_code', 'N/A')}")
        
        self._logger.sucesso("Meta definida com sucesso no servidor.")

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
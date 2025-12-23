"""
API refatorada para Microsoft Rewards.

Fornece interface para interação com a API do Microsoft Rewards
com tratamento robusto de erros e arquitetura modular.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, Any, List, Optional, Mapping, Iterable, Union
import time
import json

from raxy.interfaces.services import IRewardsDataService, ILoggingService, ISessionManager
from raxy.domain.rewards import Promotion, DailySet, RewardsDashboard, CollectionResult, TaskResult, PunchCard
from raxy.core.exceptions import (
    RewardsAPIException,
    InvalidAPIResponseException,
    DataExtractionException,
    wrap_exception,
)
from raxy.core.config import get_config
import random
from raxy.core.logging import debug_log
from .base_api import BaseAPIClient

class RewardsDataParser:
    """Parser para dados do Microsoft Rewards."""
    
    @staticmethod
    def extract_points(response_data: Dict[str, Any]) -> int:
        """
        Extrai pontos da resposta.
        
        Args:
            response_data: Dados da resposta
            
        Returns:
            int: Pontos disponíveis
        """
        dashboard = RewardsDataParser._get_dashboard(response_data)
        try:
            return int(dashboard.get("userStatus", {}).get("availablePoints", 0))
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def extract_user_status(response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrai status completo do usuário.
        
        Args:
            response_data: Dados da resposta
            
        Returns:
            Dict[str, Any]: Status do usuário
        """
        dashboard = RewardsDataParser._get_dashboard(response_data)
        return dashboard.get("userStatus", {})

    @staticmethod
    def _get_dashboard(response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Valida e extrai o objeto dashboard."""
        if not isinstance(response_data, dict):
             # Se for None ou outro tipo
             if response_data is None:
                 return {}
             raise InvalidAPIResponseException("Resposta da API não é um dicionário válido")
        
        dashboard = response_data.get("dashboard")
        if not isinstance(dashboard, dict):
            # Fallback: Tenta encontrar chaves conhecidas no root se o dashboard não existir
            if "userStatus" in response_data: 
                return response_data
            # Retorna vazio se não conseguir extrair, para evitar quebras abruptas em métodos opcionais
            # Mas se for extract_points, vai dar erro lá.
            return {}
        return dashboard

    @staticmethod
    def parse_promotion(item: Dict[str, Any], date_ref: Optional[str] = None) -> Promotion:
        """
        Monta objeto de promoção dos dados brutos.
        
        Args:
            item: Item de promoção
            date_ref: Data de referência
            
        Returns:
            Promotion: Objeto de promoção
        """
        # Extrai atributos, tolerante a falhas
        attributes = item.get("attributes", {})
        if not isinstance(attributes, dict):
            attributes = {}
        
        # Helper para extrair valor de múltiplos lugares
        def get_val(*keys) -> Any:
            for k in keys:
                val = item.get(k) or attributes.get(k)
                if val: return val
            return None

        # Identificação
        name = get_val("name", "offerId") or ""
        identifier = item.get("offerId") or name
        
        # Pontos
        points = 0
        try:
            points = (
                RewardsDataParser._to_int(item.get("pointProgressMax")) or
                RewardsDataParser._to_int(attributes.get("max")) or
                RewardsDataParser._to_int(attributes.get("pts")) or
                0
            )
        except Exception:
            pass
        
        # Status
        complete = bool(item.get("complete"))
        if not complete and isinstance(attributes.get("complete"), str):
            complete = attributes.get("complete").lower() == "true"
            
        # URL
        url = get_val("destinationUrl", "destination", "url")
        
        # Título e Descrição
        title = get_val("title", "link_text") or ""
        desc = get_val("description", "shortDescription")
        
        # Hash (importante para execução)
        promo_hash = item.get("hash")
        
        # Tipo
        promo_type = get_val("type", "promotionType", "promotionSubtype")

        # Metadados limpos
        metadata = {k: v for k, v in item.items() 
                   if k not in ["attributes", "name", "offerId", "hash", "title", "description", 
                                "pointProgressMax", "complete", "destinationUrl", "imageUrl"]}
        
        # Progress
        point_progress = (
            RewardsDataParser._to_int(item.get("pointProgress")) or
            RewardsDataParser._to_int(attributes.get("progress")) or
            0
        )
        point_progress_max = (
            RewardsDataParser._to_int(item.get("pointProgressMax")) or
            RewardsDataParser._to_int(attributes.get("max")) or
            0
        )

        return Promotion(
            id=str(identifier),
            hash=str(promo_hash) if promo_hash else None,
            title=str(title),
            description=str(desc) if desc else None,
            points=points,
            complete=complete,
            url=url,
            date=date_ref,
            type=str(promo_type) if promo_type else None,
            point_progress=point_progress,
            point_progress_max=point_progress_max,
            metadata=metadata
        )
    
    @staticmethod
    def parse_punch_card(item: Dict[str, Any]) -> PunchCard:
        """
        Parser para Punch Cards.
        
        Args:
            item: Item do punch card
            
        Returns:
            PunchCard: Objeto estruturado
        """
        try:
            parent_raw = item.get("parentPromotion")
            parent = RewardsDataParser.parse_promotion(parent_raw) if isinstance(parent_raw, dict) else None
            
            children = []
            for child_raw in item.get("childPromotions", []):
                if isinstance(child_raw, dict):
                    children.append(RewardsDataParser.parse_promotion(child_raw))
            
            return PunchCard(
                name=str(item.get("name") or (parent.title if parent else "Unknown PunchCard")),
                parent_promotion=parent,
                child_promotions=children
            )
        except Exception as e:
            # Fallback robusto
            debug_log(f"Erro ao parsear punch card: {e}")
            return PunchCard(name=str(item.get("name", "Error")), child_promotions=[])

    @staticmethod
    def _to_int(value: Any) -> Optional[int]:
        """Converte valor para inteiro com segurança."""
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str) and value.strip():
            # Remove caracteres não numéricos exceto se for só digitos
            if value.isdigit():
                return int(value)
            # Tenta extrair dígitos simples
            digits = "".join(filter(str.isdigit, value))
            if digits:
                return int(digits)
        return None


class RewardsDataAPI(BaseAPIClient, IRewardsDataService):
    """
    Cliente de API para Microsoft Rewards.
    
    Oferece métodos completos para obter e manipular dados do dashboard.
    """
    
    def __init__(
        self,
        logger: Optional[ILoggingService] = None,
        palavras_erro: Optional[Iterable[str]] = None,
    ) -> None:
        super().__init__(
            logger=logger,
            error_words=palavras_erro or get_config().api.rewards_error_words
        )
        self.parser = RewardsDataParser()
    
    @debug_log(log_result=True, log_duration=True)
    def obter_pontos(self, sessao: ISessionManager, *, bypass_request_token: bool = True) -> int:
        """Obtém apenas o saldo de pontos atual."""
        self.logger.debug("Obtendo saldo de pontos")
        response_data = self._fetch_dashboard(sessao, bypass_request_token)
        return self.parser.extract_points(response_data)

    @debug_log(log_result=False, log_duration=True)
    def obter_recompensas(
        self,
        sessao: ISessionManager,
        *,
        bypass_request_token: bool = True,
    ) -> RewardsDashboard:
        """
        Obtém o dashboard completo de recompensas.
        
        Inclui conjuntos diários, promoções extras, punch cards e status do usuário.
        """
        self.logger.debug("Obtendo dashboard completo")
        response_data = self._fetch_dashboard(sessao, bypass_request_token)
        
        # 1. Dados Brutos e Validação
        if response_data is None:
            return RewardsDashboard(raw_data={"error": "No response data"})

        if not isinstance(response_data, dict):
            return RewardsDashboard(raw_data={"error": "Invalid response format"})
            
        dashboard_data = response_data.get("dashboard", {})
        if not dashboard_data and "dashboard" not in response_data:
             # Se a resposta for o próprio dashboard (caso raro mas possível em algumas APIs)
             if "userStatus" in response_data:
                 dashboard_data = response_data
        
        if not isinstance(dashboard_data, dict):
             dashboard_data = {}

        # 2. Daily Sets
        daily_sets = []
        for date_key, items in dashboard_data.get("dailySetPromotions", {}).items():
            if isinstance(items, list):
                promos = [self.parser.parse_promotion(i, date_key) for i in items if isinstance(i, dict)]
                if promos:
                    daily_sets.append(DailySet(date=date_key, promotions=promos))

        # 3. More Promotions (e variações)
        more_promotions = []
        # Combina listas comuns de promoções extras
        extra_keys = ["morePromotions", "promotionalItems", "streakBonusPromotions"] 
        for key in extra_keys:
            items_list = dashboard_data.get(key)
            if isinstance(items_list, list):
                for item in items_list:
                    if isinstance(item, dict):
                        more_promotions.append(self.parser.parse_promotion(item))
        
        # 4. Punch Cards
        punch_cards = []
        pc_list = dashboard_data.get("punchCards")
        if isinstance(pc_list, list):
            for item in pc_list:
                if isinstance(item, dict):
                    punch_cards.append(self.parser.parse_punch_card(item))
        
        # 5. Promotional Items (Separated specifically if needed, or included in more_promotions)
        promotional_items = []
        pi_list = dashboard_data.get("promotionalItems")
        if isinstance(pi_list, list):
             for item in pi_list:
                 if isinstance(item, dict):
                     promotional_items.append(self.parser.parse_promotion(item))

        # 6. User Status
        user_status = dashboard_data.get("userStatus", {})

        self.logger.info(
            f"Dashboard processado: {len(daily_sets)} daily sets, "
            f"{len(more_promotions)} extras, {len(punch_cards)} punch cards"
        )
        
        return RewardsDashboard(
            daily_sets=daily_sets,
            more_promotions=more_promotions,
            punch_cards=punch_cards,
            promotional_items=promotional_items,
            user_status=user_status,
            raw_data=response_data
        )

    @debug_log(log_result=False, log_duration=True)
    def pegar_recompensas(
        self,
        sessao: ISessionManager,
        *,
        bypass_request_token: bool = True,
    ) -> CollectionResult:
        """Coleta todas as recompensas viáveis (Daily Sets e More Promotions)."""
        dashboard = self.obter_recompensas(sessao, bypass_request_token=bypass_request_token)
        collection_result = CollectionResult()
        
        if not dashboard.all_promotions:
            self.logger.info("Nenhuma tarefa disponível para execução.")
            return collection_result

        template_base = self.load_template(get_config().api.rewards.template_executar_tarefa)
        
        # 1. Process Daily Sets (Iterate all days)
        for daily_set in dashboard.daily_sets:
            self.logger.info(f"Processando Daily Set: {daily_set.date}")
            self._process_promotions_list(sessao, template_base, daily_set.promotions, collection_result)

        # 2. Process Punch Cards
        if dashboard.punch_cards:
             self.logger.info(f"Processando {len(dashboard.punch_cards)} Punch Cards")
             for pc in dashboard.punch_cards:
                 to_process = []
                 if pc.parent_promotion: to_process.append(pc.parent_promotion)
                 to_process.extend(pc.child_promotions)
                 self._process_promotions_list(sessao, template_base, to_process, collection_result)
        
        # 3. More Promotions & Items
        if dashboard.more_promotions:
            self.logger.info("Processando More Promotions")
            self._process_promotions_list(sessao, template_base, dashboard.more_promotions, collection_result)
            
        if dashboard.promotional_items:
            self.logger.info("Processando Promotional Items")
            self._process_promotions_list(sessao, template_base, dashboard.promotional_items, collection_result)

        return collection_result

    def _process_promotions_list(
        self,
        sessao: ISessionManager,
        template_base: Dict[str, Any],
        promotions: List[Promotion],
        collection_result: CollectionResult
    ) -> None:
        """Helper para processar lista de promoções."""
        for promo in promotions:
            if not promo.complete:
                if promo.type == "urlreward" and promo.point_progress_max <= 0:
                     continue
                     
                if promo.type == "quiz":
                    self._execute_quiz(sessao, promo, collection_result)
                else:
                    self._execute_promotion(sessao, template_base, promo, collection_result)

    def _fetch_dashboard(self, sessao: ISessionManager, bypass_token: bool) -> Dict[str, Any]:
        """Método interno para buscar o JSON do dashboard."""
        return self.execute_template_and_parse(
            sessao=sessao,
            template=self.load_template(get_config().api.rewards.template_obter_pontos),
            bypass_request_token=bypass_token,
            exception_type=RewardsAPIException,
            error_message="Falha ao obter dados do Rewards",
            context={"template": "rewards_obter_pontos"}
        )

    def _execute_quiz(
        self,
        sessao: ISessionManager,
        promotion: Promotion,
        result_accumulator: CollectionResult
    ) -> None:
        """Executa tarefa do tipo quiz/questionário."""
        start_time = time.time()
        
        # Inicializa controle de loop
        attempts = 0
        max_attempts = 10
        
        self.logger.debug(f"Executando Quiz {promotion.id}. Max tentativas: {max_attempts}")
        
        success_count = 0
        
        try:
             # Carrega o template configurado
             template_name = get_config().api.rewards.template_quiz
             template_base = self.load_template(template_name)
             
             # Loop enquanto não completar e não exceder tentativas
             while promotion.point_progress < promotion.point_progress_max and attempts < max_attempts:
                 attempts += 1
                 
                 self.logger.info(f"Quiz {promotion.title or promotion.id}: Tentativa {attempts}/{max_attempts}. Progresso: {promotion.point_progress}/{promotion.point_progress_max}")

                 # Prepara template deepcopy para cada iteração
                 template = deepcopy(template_base)
                 
                 # Atualiza Headers (Referer)
                 if "headers" in template and "Referer" in template["headers"]:
                     template["headers"]["Referer"] = template["headers"]["Referer"].replace("{offerId}", promotion.id)

                 # Atualiza Data (Payload) output
                 if "data" in template:
                      if isinstance(template["data"], str):
                          # Payload é string JSON com placeholders (ex: "{{...}}")
                          try:
                              template["data"] = template["data"].format(
                                  offerId=promotion.id,
                                  questionIndex="-1"
                              )
                          except Exception:
                              # Fallback simples
                              template["data"] = template["data"].replace("{offerId}", promotion.id).replace("{questionIndex}", "-1")
                      else:
                          # Payload é dict (legado/fallback)
                          template["data"]["OfferId"] = promotion.id
                          template["data"]["QuestionIndex"] = "-1"
 
                  # Executa request
                 resp = self._execute_request(
                     sessao,
                     template,
                     bypass_request_token=False,
                     error_context=f"quiz_iter_{attempts}"
                 )
                 
                 # Verifica sucesso request
                 if getattr(resp, "ok", False) or (hasattr(resp, "status_code") and 200 <= resp.status_code < 300):
                     success_count += 1
                     
                     # 3. Pull (Fetch) updated data "toda vez"
                     try:
                         # 2-3s delay antes do refresh
                         time.sleep(random.uniform(2.0, 3.0))
                         
                         # Refetch dashboard (bypass token true to match usage pattern)
                         new_dashboard = self.obter_recompensas(sessao, bypass_request_token=True)
                         
                         # Encontra a promoção atualizada
                         updated_promo = next((p for p in new_dashboard.all_promotions if p.id == promotion.id), None)
                         
                         if updated_promo:
                             self.logger.debug(f"Atualizando status do Quiz: {updated_promo.point_progress}/{updated_promo.point_progress_max}")
                             promotion.point_progress = updated_promo.point_progress
                             promotion.point_progress_max = updated_promo.point_progress_max
                             promotion.complete = updated_promo.complete
                         else:
                             self.logger.aviso(f"Promoção {promotion.id} não encontrada após refresh. Parando.")
                             break
                             
                     except Exception as fetch_err:
                         self.logger.erro(f"Erro ao obter status atualizado do quiz: {fetch_err}")
                         # Em caso de erro no refresh, continuamos para não abortar fluxo se for intermitente
                         pass

                 else:
                     self.logger.aviso(f"Falha no quiz {promotion.id} tentativa {attempts}")
                     time.sleep(5)
            
             result_accumulator.add_result(TaskResult(
                promotion_id=promotion.id,
                success=success_count > 0,
                points_earned=0, # Difícil calcular exato sem diff
                duration_seconds=time.time() - start_time
             ))

        except Exception as e:
            self.logger.erro(f"Erro executando quiz {promotion.id}: {e}")
            result_accumulator.add_result(TaskResult(
                promotion_id=promotion.id,
                success=False,
                error=str(e),
                duration_seconds=time.time() - start_time
            ))

    def _execute_promotion(
        self, 
        sessao: ISessionManager, 
        template_base: Dict[str, Any], 
        promotion: Promotion, 
        result_accumulator: CollectionResult
    ) -> None:
        """Executa uma única promoção e registra o resultado."""
        if not promotion.id or not promotion.hash:
            return # Pula inválidos

        start_time = time.time()
        try:
            # Prepara payload
            template = deepcopy(template_base)
            template["data"] = {
                **template.get("data", {}),
                "id": promotion.id,
                "hash": promotion.hash,
                "__RequestVerificationToken": sessao.token_antifalsificacao
            }

            # Executa
            self.logger.debug(f"Executando tarefa: {promotion.title} ({promotion.id})")
            response = self._execute_request(
                sessao, template, 
                bypass_request_token=False,
                error_context=f"promo={promotion.id}"
            )
            
            # Verifica sucesso (simplificado)
            is_ok = getattr(response, "ok", False)
            points = promotion.points if is_ok else 0
            
            result_accumulator.add_result(TaskResult(
                promotion_id=promotion.id,
                success=is_ok,
                points_earned=points,
                duration_seconds=time.time() - start_time
            ))
            
        except Exception as e:
            self.logger.aviso(f"Erro na tarefa {promotion.id}: {e}")
            result_accumulator.add_result(TaskResult(
                promotion_id=promotion.id,
                success=False,
                error=str(e),
                duration_seconds=time.time() - start_time
            ))

    # Métodos utilitários de manipulação e consulta
    
    def get_user_level(self, dashboard: RewardsDashboard) -> str:
        """Retorna o nível atua do usuário (ex: 'Level 2')."""
        info = dashboard.user_status.get("levelInfo", {})
        if not isinstance(info, dict): return "Unknown"
        return str(info.get("activeLevelName", "Unknown"))
        
    def get_pc_search_progress(self, dashboard: RewardsDashboard) -> tuple[int, int]:
        """Retorna (progresso, total) da busca PC."""
        counters = dashboard.user_status.get("counters", {}).get("pcSearch", [])
        if not isinstance(counters, list) or not counters: return (0, 0)
        # Assume o primeiro contador de PC Search relevante
        c = counters[0]
        if not isinstance(c, dict): return (0, 0)
        return (self.parser._to_int(c.get("pointProgress")) or 0, 
                self.parser._to_int(c.get("pointProgressMax")) or 0)
        
    def get_mobile_search_progress(self, dashboard: RewardsDashboard) -> tuple[int, int]:
        """Retorna (progresso, total) da busca Mobile."""
        counters = dashboard.user_status.get("counters", {}).get("mobileSearch", [])
        if not isinstance(counters, list) or not counters: return (0, 0)
        c = counters[0]
        if not isinstance(c, dict): return (0, 0)
        return (self.parser._to_int(c.get("pointProgress")) or 0, 
                self.parser._to_int(c.get("pointProgressMax")) or 0)

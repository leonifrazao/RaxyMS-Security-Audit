"""
API refatorada para Microsoft Rewards.

Fornece interface para interação com a API do Microsoft Rewards
com tratamento robusto de erros e arquitetura modular.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Dict, Any, List, Optional, Mapping, Iterable

from raxy.core.exceptions import (
    RewardsAPIException,
    InvalidAPIResponseException,
    DataExtractionException,
    wrap_exception,
)
from raxy.infrastructure.config.config import get_config
from raxy.infrastructure.logging import debug_log
from .base_api import BaseAPIClient


# Constantes locais
TEMPLATE_OBTER_PONTOS = "rewards_obter_pontos.json"
TEMPLATE_EXECUTAR_TAREFA = "pegar_recompensa_rewards.json"


class RewardsDataParser:
    """Parser para dados do Microsoft Rewards."""
    
    @staticmethod
    def extract_points(response_data: Dict[str, Any]) -> int:
        """Extrai pontos da resposta."""
        if not isinstance(response_data, dict) or "dashboard" not in response_data:
            raise InvalidAPIResponseException(
                "Formato de resposta inesperado",
                details={"has_dashboard": "dashboard" in response_data if isinstance(response_data, dict) else False}
            )
        
        try:
            return int(response_data["dashboard"]["userStatus"]["availablePoints"])
        except (KeyError, ValueError, TypeError) as e:
            raise wrap_exception(e, DataExtractionException, "Erro ao extrair pontos da resposta")
    
    @staticmethod
    def parse_promotion(item: Dict[str, Any], date_ref: Optional[str] = None) -> Dict[str, Any]:
        """Monta objeto de promoção dos dados brutos."""
        attributes = item.get("attributes", {}) if isinstance(item.get("attributes"), dict) else {}
        
        # Extrai pontos
        points = (
            RewardsDataParser._to_int(item.get("pointProgressMax")) or
            RewardsDataParser._to_int(attributes.get("max")) or
            RewardsDataParser._to_int(attributes.get("link_text"))
        )
        
        # Extrai tipo
        promo_type = None
        for key in ("type", "promotionType", "promotionSubtype"):
            value = item.get(key) or attributes.get(key)
            if isinstance(value, str) and value.strip():
                promo_type = value.strip()
                break
        
        # Status de completude
        complete = bool(item.get("complete"))
        
        return {
            "id": item.get("name") or item.get("offerId"),
            "hash": item.get("hash"),
            "title": item.get("title") or attributes.get("title"),
            "description": item.get("description") or attributes.get("description"),
            "points": points,
            "complete": complete,
            "url": item.get("destinationUrl") or attributes.get("destination"),
            "date": date_ref,
            "type": promo_type,
        }
    
    @staticmethod
    def _to_int(value: Any) -> Optional[int]:
        """Converte valor para inteiro."""
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            digits = [ch for ch in value if ch.isdigit()]
            if digits:
                return int("".join(digits))
        return None


class RewardsDataAPI(BaseAPIClient):
    """
    Cliente de API para Microsoft Rewards.
    
    Uso:
        api = RewardsDataAPI(session=session_manager)
        pontos = api.obter_pontos()
        recompensas = api.obter_recompensas()
    """
    
    def __init__(
        self,
        session: Optional[Any] = None,
        logger: Optional[Any] = None,
        palavras_erro: Optional[Iterable[str]] = None,
    ) -> None:
        config = get_config()
        base_url = config.session.rewards_url if hasattr(config, 'session') else "https://rewards.bing.com"
        
        super().__init__(
            base_url=base_url,
            session=session,
            logger=logger,
            error_words=palavras_erro
        )
        
        cookie_count = len(self.cookies)
        self.logger.debug(f"RewardsDataAPI inicializada com {cookie_count} cookies")
        
        self.parser = RewardsDataParser()
        self._token_antifalsificacao: Optional[str] = None
        
        # Se tiver sessão, pega o token
        if session is not None:
            self._token_antifalsificacao = getattr(session, 'token_antifalsificacao', None)
    
    def set_session(self, session: Any) -> None:
        """Configura a sessão e atualiza token."""
        super().set_session(session)
        self._token_antifalsificacao = getattr(session, 'token_antifalsificacao', None)

    @debug_log(log_result=True, log_duration=True)
    def obter_pontos(self) -> int:
        """
        Obtém os pontos disponíveis.
        
        Returns:
            int: Pontos disponíveis
        """
        self.logger.debug("Obtendo pontos do Rewards")
        
        # Carrega template
        template = self.load_and_copy_template(TEMPLATE_OBTER_PONTOS)
        
        # Executa requisição
        response = self.execute_template(template)
        
        # Extrai pontos
        points = self.parser.extract_points(response if isinstance(response, dict) else {})
        
        self.logger.info(f"Pontos obtidos: {points}")
        return points

    @debug_log(log_result=False, log_duration=True)
    def obter_recompensas(self) -> Mapping[str, Any]:
        """
        Obtém as recompensas disponíveis.
        
        Returns:
            Mapping[str, Any]: Recompensas formatadas
        """
        self.logger.debug("Obtendo recompensas disponíveis")
        
        # Carrega template
        template = self.load_and_copy_template(TEMPLATE_OBTER_PONTOS)
        
        # Executa requisição
        response_data = self.execute_template(template)
        
        if not isinstance(response_data, dict):
            return {"daily_sets": [], "more_promotions": [], "error": "Resposta inválida"}
        
        dashboard = response_data.get("dashboard")
        if not isinstance(dashboard, dict):
            return {"daily_sets": [], "more_promotions": [], "error": "Dashboard ausente"}
        
        # Processa promoções
        more_promotions = []
        for item in dashboard.get("morePromotions", []):
            if isinstance(item, dict):
                try:
                    more_promotions.append(self.parser.parse_promotion(item))
                except Exception as e:
                    self.logger.debug(f"Erro ao processar promoção: {e}")
        
        # Processa conjuntos diários
        daily_sets = []
        for date_ref, items in dashboard.get("dailySetPromotions", {}).items():
            if isinstance(items, list):
                promotions = []
                for item in items:
                    if isinstance(item, dict):
                        try:
                            promotions.append(self.parser.parse_promotion(item, date_ref))
                        except Exception as e:
                            self.logger.debug(f"Erro ao processar promoção diária: {e}")
                
                if promotions:
                    daily_sets.append({"date": date_ref, "promotions": promotions})
        
        self.logger.info(
            f"Recompensas obtidas: {len(daily_sets)} conjuntos diários, "
            f"{len(more_promotions)} promoções adicionais"
        )
        
        return {
            "daily_sets": daily_sets,
            "more_promotions": more_promotions,
            "raw": response_data,
            "raw_dashboard": dashboard,
        }

    @debug_log(log_result=False, log_duration=True)
    def pegar_recompensas(self) -> Mapping[str, Any]:
        """
        Coleta as recompensas disponíveis.
        
        Returns:
            Mapping[str, Any]: Resultado das coletas
        """
        self.logger.debug("Iniciando coleta de recompensas")
        
        recompensas = self.obter_recompensas()
        daily_sets = recompensas.get("daily_sets", [])
        more_promotions = recompensas.get("more_promotions", [])

        if not daily_sets and not more_promotions:
            self.logger.info("Nenhuma recompensa para coletar")
            return {"daily_sets": [], "more_promotions": []}
        
        # Carrega template de execução
        template_base = self._load_execution_template()
        
        # Processa conjuntos diários
        daily_results = []
        for daily_set in daily_sets:
            date_ref = daily_set.get("date")
            result = self._process_promotions(template_base, daily_set.get("promotions", []), date_ref)
            if result.get("promotions"):
                daily_results.append(result)
        
        # Processa promoções adicionais
        more_results = []
        if more_promotions:
            result = self._process_promotions(template_base, more_promotions)
            if result.get("promotions"):
                more_results = result["promotions"]
        
        self.logger.info(
            f"Recompensas coletadas: {len(daily_results)} conjuntos, "
            f"{len(more_results)} promoções"
        )
        
        return {
            "daily_sets": daily_results,
            "more_promotions": more_results,
        }
    
    def _load_execution_template(self) -> Dict[str, Any]:
        """Carrega template de execução de tarefa."""
        try:
            return self.load_and_copy_template(TEMPLATE_EXECUTAR_TAREFA)
        except FileNotFoundError:
            return {"data": {}}
    
    def _process_promotions(
        self,
        template_base: Dict[str, Any],
        promotions: List[Dict[str, Any]],
        date_ref: Optional[str] = None
    ) -> Dict[str, Any]:
        """Processa lista de promoções."""
        results = []
        
        for promotion in promotions:
            promo_id = promotion.get("id")
            promo_hash = promotion.get("hash")
            
            if not promo_id or not promo_hash:
                continue
            
            # Prepara template para esta promoção
            template = deepcopy(template_base)
            payload = dict(template.get("data", {}))
            payload.update({
                "id": promo_id,
                "hash": promo_hash,
                "__RequestVerificationToken": self._token_antifalsificacao
            })
            template["data"] = payload
            
            # Executa
            try:
                response = self.execute_template(template)
                
                is_ok = isinstance(response, dict) and response.get("success", False)
                
                results.append({
                    "id": promo_id,
                    "hash": promo_hash,
                    "ok": is_ok,
                })
                
                self.logger.debug(f"Promoção processada: {promo_id}")
                
            except Exception as e:
                results.append({
                    "id": promo_id,
                    "hash": promo_hash,
                    "ok": False,
                    "error": str(e),
                })
                self.logger.debug(f"Erro em promoção {promo_id}: {e}")
        
        if date_ref:
            return {"date": date_ref, "promotions": results}
        return {"promotions": results}

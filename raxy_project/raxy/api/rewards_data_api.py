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
    JSONParsingException,
    DataExtractionException,
    wrap_exception,
)
from raxy.core.config import get_config
from raxy.core.logging import debug_log
from .base_api import BaseAPIClient


# Constantes locais (não configuráveis)
BASE_URL = "https://rewards.microsoft.com"
TEMPLATE_OBTER_PONTOS = "rewards_obter_pontos.json"
TEMPLATE_EXECUTAR_TAREFA = "pegar_recompensa_rewards.json"


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
            
        Raises:
            DataExtractionException: Se erro ao extrair
        """
        if not isinstance(response_data, dict) or "dashboard" not in response_data:
            raise InvalidAPIResponseException(
                "Formato de resposta inesperado",
                details={"has_dashboard": "dashboard" in response_data if isinstance(response_data, dict) else False}
            )
        
        try:
            return int(response_data["dashboard"]["userStatus"]["availablePoints"])
        except (KeyError, ValueError, TypeError) as e:
            raise wrap_exception(
                e, DataExtractionException,
                "Erro ao extrair pontos da resposta",
                response_keys=list(response_data.keys()) if isinstance(response_data, dict) else None
            )
    
    @staticmethod
    def parse_promotion(item: Dict[str, Any], date_ref: Optional[str] = None) -> Dict[str, Any]:
        """
        Monta objeto de promoção dos dados brutos.
        
        Args:
            item: Item de promoção
            date_ref: Data de referência
            
        Returns:
            Dict[str, Any]: Promoção formatada
        """
        # Extrai atributos
        attributes = {}
        try:
            attrs_obj = item.get("attributes")
            attributes = attrs_obj if isinstance(attrs_obj, dict) else {}
        except Exception:
            pass
        
        # Extrai pontos
        points = None
        try:
            points = (
                RewardsDataParser._to_int(item.get("pointProgressMax")) or
                RewardsDataParser._to_int(attributes.get("max")) or
                RewardsDataParser._to_int(attributes.get("link_text"))
            )
        except Exception:
            pass
        
        # Extrai tipo
        promo_type = None
        try:
            for key in ("type", "promotionType", "promotionSubtype"):
                value = item.get(key)
                if not isinstance(value, str) and isinstance(attributes.get(key), str):
                    value = attributes.get(key)
                if isinstance(value, str) and value.strip():
                    promo_type = value.strip()
                    break
        except Exception:
            pass
        
        # Extrai status de completude
        complete = False
        try:
            complete = bool(item.get("complete"))
            complete_attr = attributes.get("complete")
            if isinstance(complete_attr, str) and not complete:
                complete = complete_attr.strip().lower() == "true"
        except Exception:
            pass
        
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
    
    Implementa a interface IRewardsDataService com arquitetura modular
    e tratamento robusto de erros.
    """
    
    def __init__(
        self,
        logger: Optional[Any] = None,
        palavras_erro: Optional[Iterable[str]] = None,
    ) -> None:
        """
        Inicializa o cliente de Rewards.
        
        Args:
            logger: Serviço de logging
            palavras_erro: Palavras que indicam erro na resposta
        """
        super().__init__(
            base_url=BASE_URL,
            logger=logger,
            error_words=palavras_erro or get_config().api.rewards_error_words
        )
        
        self.parser = RewardsDataParser()

    @debug_log(log_result=True, log_duration=True)
    def obter_pontos(self, sessao: Any, *, bypass_request_token: bool = True) -> int:
        """
        Obtém os pontos disponíveis.
        
        Args:
            sessao: Sessão do usuário
            bypass_request_token: Se deve bypass do token
            
        Returns:
            int: Pontos disponíveis
            
        Raises:
            RewardsAPIException: Se erro na API
        """
        self.logger.debug("Obtendo pontos do Rewards")
        
        # Carrega template
        template_path = self.TEMPLATES_DIR / TEMPLATE_OBTER_PONTOS
        
        try:
            response = sessao.execute_template(
                template_path,
                bypass_request_token=bypass_request_token
            )
        except Exception as e:
            raise wrap_exception(
                e, RewardsAPIException,
                "Erro ao executar template de pontos",
                template=str(template_path)
            )
        
        # Valida resposta
        self.validate_response(response, context_info={"template": str(template_path)})
        
        # Parse JSON
        response_data = self.safe_json_parse(response)
        
        # Extrai pontos
        points = self.parser.extract_points(response_data)
        
        self.logger.info(f"Pontos obtidos: {points}")
        

        
        return points

    @debug_log(log_result=False, log_duration=True)
    def obter_recompensas(
        self,
        sessao: Any,
        *,
        bypass_request_token: bool = True,
    ) -> Mapping[str, Any]:
        """
        Obtém as recompensas disponíveis.
        
        Args:
            sessao: Sessão do usuário
            bypass_request_token: Se deve bypass do token
            
        Returns:
            Mapping[str, Any]: Recompensas formatadas
        """
        self.logger.debug("Obtendo recompensas disponíveis")
        
        # Usa mesmo template de pontos que contém todas as infos
        template_path = self.TEMPLATES_DIR / TEMPLATE_OBTER_PONTOS
        
        try:
            response = sessao.execute_template(
                template_path,
                bypass_request_token=bypass_request_token
            )
        except Exception as e:
            raise wrap_exception(
                e, RewardsAPIException,
                "Erro ao executar template de recompensas",
                template=str(template_path)
            )
        
        # Parse JSON
        response_data = self.safe_json_parse(response)
        
        # Valida estrutura básica
        if not isinstance(response_data, dict):
            return {"daily_sets": [], "more_promotions": [], "error": "Resposta inválida"}
        
        dashboard = response_data.get("dashboard")
        if not isinstance(dashboard, dict):
            return {"daily_sets": [], "more_promotions": [], "error": "Dashboard ausente"}
        
        # Processa promoções mais
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
    def pegar_recompensas(
        self,
        sessao: Any,
        *,
        bypass_request_token: bool = True,
    ) -> Mapping[str, Any]:
        """
        Coleta as recompensas disponíveis.
        
        Args:
            sessao: Sessão do usuário
            bypass_request_token: Se deve bypass do token
            
        Returns:
            Mapping[str, Any]: Resultado das coletas
        """
        self.logger.debug("Iniciando coleta de recompensas")
        try:
            recompensas = self.obter_recompensas(sessao, bypass_request_token=bypass_request_token)
        except Exception as e:
            raise wrap_exception(
                e, RewardsAPIException,
                "Erro ao obter lista de recompensas"
            )

        daily_sets = recompensas.get("daily_sets", []) if isinstance(recompensas, dict) else []
        more_promotions = recompensas.get("more_promotions", []) if isinstance(recompensas, dict) else []

        if not daily_sets and not more_promotions:
            self.logger.info("Nenhuma recompensa para coletar")
            return {"daily_sets": [], "more_promotions": []}
        
        # Carrega template de execução
        template_base = self._load_execution_template()
        
        # Processa conjuntos diários
        daily_results = []
        for daily_set in daily_sets:
            date_ref = daily_set.get("date")
            result = self._process_promotions(
                sessao,
                template_base,
                daily_set.get("promotions", []),
                date_ref
            )
            if result.get("promotions"):
                daily_results.append(result)
        
        # Processa promoções adicionais
        more_results = []
        if more_promotions:
            result = self._process_promotions(
                sessao,
                template_base,
                more_promotions
            )
            if result.get("promotions"):
                more_results = result["promotions"]
        
        # Calcula estatísticas
        total_tasks = sum(len(ds.get("promotions", [])) for ds in daily_results) + len(more_results)
        tasks_completed = sum(
            1 for ds in daily_results 
            for promo in ds.get("promotions", []) 
            if promo.get("ok")
        ) + sum(1 for promo in more_results if promo.get("ok"))
        tasks_failed = total_tasks - tasks_completed
        
        self.logger.info(
            f"Recompensas coletadas: {len(daily_results)} conjuntos, "
            f"{len(more_results)} promoções"
        )
        

        
        return {
            "daily_sets": daily_results,
            "more_promotions": more_results,
        }
    
    def _load_execution_template(self) -> Dict[str, Any]:
        """
        Carrega template de execução de tarefa.
        
        Returns:
            Dict[str, Any]: Template carregado
        """
        template_path = self.TEMPLATES_DIR / TEMPLATE_EXECUTAR_TAREFA
        
        # Cria template padrão se não existir
        if not template_path.exists():
            template_path.parent.mkdir(parents=True, exist_ok=True)
            default_template = {"data": {}}
            with open(template_path, 'w', encoding="utf-8") as f:
                json.dump(default_template, f)
            return default_template
        
        # Carrega template existente
        try:
            with open(template_path, encoding="utf-8") as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            raise wrap_exception(
                e, RewardsAPIException,
                "Erro ao carregar template de execução",
                template=str(template_path)
            )
    
    def _process_promotions(
        self,
        sessao: Any,
        template_base: Dict[str, Any],
        promotions: List[Dict[str, Any]],
        date_ref: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processa lista de promoções.
        
        Args:
            sessao: Sessão do usuário
            template_base: Template base para execução
            promotions: Lista de promoções
            date_ref: Data de referência
            
        Returns:
            Dict[str, Any]: Resultado do processamento
        """
        results = []
        
        for promotion in promotions:
            promo_id = promotion.get("id")
            promo_hash = promotion.get("hash")
            
            if not promo_id or not promo_hash:
                self.logger.debug(f"Promoção sem ID/hash: {promotion}")
                continue
            
            # Prepara template para esta promoção
            template = deepcopy(template_base)
            payload = dict(template.get("data", {}))
            payload.update({
                "id": promo_id,
                "hash": promo_hash,
                "__RequestVerificationToken": sessao.token_antifalsificacao
            })
            template["data"] = payload
            
            # Executa e registra resultado
            try:
                response = sessao.execute_template(
                    template,
                    bypass_request_token=False
                )
                
                is_ok = bool(getattr(response, "ok", False))
                status_code = getattr(response, "status_code", None)
                
                results.append({
                    "id": promo_id,
                    "hash": promo_hash,
                    "ok": is_ok,
                    "status_code": status_code,
                })
                
                self.logger.debug(f"Promoção processada: {promo_id}")
                


                
            except RewardsAPIException as e:
                results.append({
                    "id": promo_id,
                    "hash": promo_hash,
                    "ok": False,
                    "status_code": None,
                    "error": str(e),
                    "error_type": "RewardsAPIException",
                })
                self.logger.debug(f"Erro em promoção {promo_id}: {e}")
                

                
            except Exception as e:
                results.append({
                    "id": promo_id,
                    "hash": promo_hash,
                    "ok": False,
                    "status_code": None,
                    "error": repr(e),
                    "error_type": type(e).__name__,
                })
                self.logger.debug(f"Erro inesperado em promoção {promo_id}: {e}")
                

        
        # Formata resultado
        if date_ref:
            return {"date": date_ref, "promotions": results}
        return {"promotions": results}


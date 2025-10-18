"""Camada de API para consumo das chamadas HTTP do Microsoft Rewards usando SessionManagerService."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Iterable, Mapping

from raxy.interfaces.services import IRewardsDataService
from raxy.core.session_manager_service import SessionManagerService
from raxy.core.exceptions import (
    RewardsAPIException,
    InvalidAPIResponseException,
    JSONParsingException,
    DataExtractionException,
    wrap_exception,
)

REQUESTS_DIR = Path(__file__).resolve().parent / "requests_templates"


class RewardsDataAPI(IRewardsDataService):
    _TEMPLATE_OBTER_PONTOS = "rewards_obter_pontos.json"
    _TEMPLATE_EXECUTAR_TAREFA = "pegar_recompensa_rewards.json"

    def __init__(
        self,
        palavras_erro: Iterable[str] | None = None,
    ) -> None:
        self._palavras_erro = tuple(palavra.lower() for palavra in palavras_erro or ("captcha", "temporarily unavailable", "error"))

    def obter_pontos(self, sessao: SessionManagerService, *, bypass_request_token: bool = True) -> int:
        """Obtém os pontos disponíveis com tratamento robusto de erros."""
        caminho_template = REQUESTS_DIR / self._TEMPLATE_OBTER_PONTOS
        
        try:
            resposta = sessao.execute_template(caminho_template, bypass_request_token=bypass_request_token)
        except Exception as e:
            raise wrap_exception(
                e, RewardsAPIException,
                "Erro ao executar template de pontos",
                template=str(caminho_template)
            )

        if resposta is None or not getattr(resposta, "ok", False):
            status = getattr(resposta, 'status_code', 'N/A')
            raise InvalidAPIResponseException(
                f"Request falhou com status {status}",
                details={"status_code": status, "template": str(caminho_template)}
            )

        try:
            resposta_json = resposta.json()
        except json.JSONDecodeError as exc:
            raise wrap_exception(
                exc, JSONParsingException,
                "Falha ao decodificar resposta JSON de pontos",
                status_code=getattr(resposta, 'status_code', None)
            )

        if not isinstance(resposta_json, dict) or "dashboard" not in resposta_json:
            raise InvalidAPIResponseException(
                "Formato de resposta inesperado ao obter pontos",
                details={"has_dashboard": "dashboard" in resposta_json if isinstance(resposta_json, dict) else False}
            )

        try:
            return int(resposta_json["dashboard"]["userStatus"]["availablePoints"])
        except (KeyError, ValueError, TypeError) as e:
            raise wrap_exception(
                e, DataExtractionException,
                "Erro ao extrair pontos da resposta",
                response_keys=list(resposta_json.keys()) if isinstance(resposta_json, dict) else None
            )

    def obter_recompensas(
        self,
        sessao: SessionManagerService,
        *,
        bypass_request_token: bool = True,
    ) -> Mapping[str, object]:
        """Obtém as recompensas disponíveis com tratamento robusto de erros."""
        caminho_template = REQUESTS_DIR / self._TEMPLATE_OBTER_PONTOS
        
        try:
            resposta = sessao.execute_template(caminho_template, bypass_request_token=bypass_request_token)
        except Exception as e:
            raise wrap_exception(
                e, RewardsAPIException,
                "Erro ao executar template de recompensas",
                template=str(caminho_template)
            )

        try:
            corpo = resposta.json()
        except json.JSONDecodeError as exc:
            raise wrap_exception(
                exc, JSONParsingException,
                "Falha ao decodificar resposta JSON de recompensas"
            )

        if not isinstance(corpo, dict):
            return {"daily_sets": [], "more_promotions": [], "error": "Resposta não é um dicionário"}

        dashboard = corpo.get("dashboard")
        if not isinstance(dashboard, dict):
            return {"daily_sets": [], "more_promotions": [], "error": "Dashboard ausente ou inválido"}

        promocoes = []
        try:
            for item in dashboard.get("morePromotions") or []:
                if isinstance(item, dict):
                    try:
                        promocoes.append(self._montar_promocao(item))
                    except Exception as e:
                        # Log mas não interrompe
                        pass
        except Exception:
            # Se falhar ao processar mais promoções, continua
            pass

        conjuntos = []
        try:
            for data_ref, itens in (dashboard.get("dailySetPromotions") or {}).items():
                if isinstance(itens, list):
                    promos_data = []
                    for it in itens:
                        if isinstance(it, dict):
                            try:
                                promos_data.append(self._montar_promocao(it, data_ref))
                            except Exception:
                                # Log mas não interrompe
                                pass
                    if promos_data:
                        conjuntos.append({"date": data_ref, "promotions": promos_data})
        except Exception:
            # Se falhar ao processar daily sets, continua
            pass

        return {
            "daily_sets": conjuntos,
            "more_promotions": promocoes,
            "raw": corpo,
            "raw_dashboard": dashboard,
        }

    def pegar_recompensas(
        self,
        sessao: SessionManagerService,
        *,
        bypass_request_token: bool = True,
    ) -> Mapping[str, object]:
        """Coleta as recompensas com tratamento de erros individual."""
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
            return {"daily_sets": [], "more_promotions": []}

        template_path = REQUESTS_DIR / self._TEMPLATE_EXECUTAR_TAREFA
        try:
            if not template_path.exists():
                template_path.parent.mkdir(parents=True, exist_ok=True)
                with open(template_path, 'w', encoding="utf-8") as f:
                    json.dump({"data": {}}, f)

            with open(template_path, encoding="utf-8") as arquivo:
                template_base = json.load(arquivo)
        except (IOError, json.JSONDecodeError) as e:
            raise wrap_exception(
                e, RewardsAPIException,
                "Erro ao carregar template de execução de tarefa",
                template=str(template_path)
            )

        def processar_promocoes(lista_promocoes: list[dict], data_referencia: str | None = None) -> Mapping[str, object]:
            promocoes_resultado = []
            for promocao in lista_promocoes:
                identificador = promocao.get("id")
                hash_promocao = promocao.get("hash")
                if not identificador or not hash_promocao:
                    continue

                template = deepcopy(template_base)
                payload = dict(template.get("data") or {})
                payload["id"] = identificador
                payload["hash"] = hash_promocao
                payload["__RequestVerificationToken"] = sessao.token_antifalsificacao
                template["data"] = payload

                try:
                    resposta = sessao.execute_template(template, bypass_request_token=False)
                except RewardsAPIException as erro:
                    promocoes_resultado.append(
                        {
                            "id": identificador,
                            "hash": hash_promocao,
                            "ok": False,
                            "status_code": None,
                            "erro": erro.message,
                            "erro_tipo": "RewardsAPIException",
                        }
                    )
                    continue
                except Exception as erro:
                    promocoes_resultado.append(
                        {
                            "id": identificador,
                            "hash": hash_promocao,
                            "ok": False,
                            "status_code": None,
                            "erro": repr(erro),
                            "erro_tipo": type(erro).__name__,
                        }
                    )
                    continue

                promocoes_resultado.append(
                    {
                        "id": identificador,
                        "hash": hash_promocao,
                        "ok": bool(getattr(resposta, "ok", False)),
                        "status_code": getattr(resposta, "status_code", None),
                    }
                )

            if data_referencia:
                return {"date": data_referencia, "promotions": promocoes_resultado}
            return {"promotions": promocoes_resultado}

        resultados_daily_sets = []
        for conjunto in daily_sets:
            data_referencia = conjunto.get("date")
            resultado = processar_promocoes(conjunto.get("promotions", []), data_referencia)
            if resultado.get("promotions"):
                resultados_daily_sets.append(resultado)

        resultados_more_promotions = []
        if more_promotions:
            resultado = processar_promocoes(more_promotions)
            if resultado.get("promotions"):
                resultados_more_promotions = resultado["promotions"]

        return {
            "daily_sets": resultados_daily_sets,
            "more_promotions": resultados_more_promotions,
        }

    def _montar_promocao(self, item: Mapping[str, object], data_ref: str | None = None) -> Mapping[str, object]:
        """Monta objeto de promoção a partir dos dados brutos."""
        try:
            atributos_obj = item.get("attributes")
            atributos = atributos_obj if isinstance(atributos_obj, dict) else {}
        except Exception:
            atributos = {}

        try:
            pontos = self._para_int(item.get("pointProgressMax")) or self._para_int(atributos.get("max")) or self._para_int(atributos.get("link_text"))
        except Exception:
            pontos = None

        tipo = None
        try:
            for chave in ("type", "promotionType", "promotionSubtype"):
                valor = item.get(chave)
                if not isinstance(valor, str) and isinstance(atributos.get(chave), str):
                    valor = atributos.get(chave)
                if isinstance(valor, str):
                    valor_limpo = valor.strip()
                    if valor_limpo:
                        tipo = valor_limpo
                        break
        except Exception:
            pass

        try:
            completo_atributo = atributos.get("complete")
            completo = bool(item.get("complete"))
            if isinstance(completo_atributo, str) and not completo:
                completo = completo_atributo.strip().lower() == "true"
        except Exception:
            completo = False

        return {
            "id": item.get("name") or item.get("offerId"),
            "hash": item.get("hash"),
            "title": item.get("title") or atributos.get("title"),
            "description": item.get("description") or atributos.get("description"),
            "points": pontos,
            "complete": completo,
            "url": item.get("destinationUrl") or atributos.get("destination"),
            "date": data_ref,
            "type": tipo,
        }

    @staticmethod
    def _para_int(valor: object) -> int | None:
        if isinstance(valor, (int, float)):
            return int(valor)
        if isinstance(valor, str):
            numeros = [ch for ch in valor if ch.isdigit()]
            if numeros:
                return int("".join(numeros))
        return None

"""Camada de API para consumo das chamadas HTTP do Microsoft Rewards."""

from __future__ import annotations

import json
import traceback
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Mapping

# Supondo que estas interfaces existam em algum lugar do seu projeto
from interfaces.services import IRewardsDataService
from core.session_service import BaseRequest

# Para o código ser autônomo, vamos criar classes dummy


REQUESTS_DIR = Path(__file__).resolve().parent / "requests_templates"


class RewardsDataAPI(IRewardsDataService):
    """Realiza chamadas HTTP autenticadas ao Rewards sem uso de navegador."""

    _TEMPLATE_OBTER_PONTOS = "rewards_obter_pontos.json"
    _TEMPLATE_EXECUTAR_TAREFA = "pegar_recompensa_rewards.json"

    def __init__(
        self,
        palavras_erro: Iterable[str] | None = None,
    ) -> None:
        self._palavras_erro = tuple(palavra.lower() for palavra in palavras_erro or ("captcha", "temporarily unavailable", "error"))


    def obter_pontos(self, base: BaseRequest, *, bypass_request_token: bool = False) -> int:
        caminho_template = REQUESTS_DIR / self._TEMPLATE_OBTER_PONTOS
        resposta = base.executar(caminho_template, bypass_request_token=bypass_request_token)

        if not getattr(resposta, "ok", True):
            self._registrar_erro(
                base,
                {"metodo": "get", "url": getattr(resposta, "url", None)},
                resposta_registro=resposta,
            )
            raise RuntimeError(f"Request falhou com status {resposta.status_code}")

        texto = (resposta.text or "").lower()
        for palavra in self._palavras_erro:
            if palavra and palavra in texto:
                self._registrar_erro(
                    base,
                    {"metodo": "get", "url": getattr(resposta, "url", None)},
                    resposta_registro=resposta,
                    extras_registro={"palavras": [palavra]},
                )
                raise RuntimeError("Request falhou: " + palavra)

        resposta_json = resposta.json()
        if not isinstance(resposta_json, dict) or "dashboard" not in resposta_json:
            self._registrar_erro(
                base,
                {"metodo": "get", "url": getattr(resposta, "url", None)},
                resposta_registro=resposta,
                extras_registro={"conteudo": resposta.text},
            )
            raise RuntimeError("Request falhou: formato inesperado")

        return int(resposta_json["dashboard"]["userStatus"]["availablePoints"])

    def obter_recompensas(
        self,
        base: BaseRequest,
        *,
        bypass_request_token: bool = False,
    ) -> Mapping[str, object]:
        caminho_template = REQUESTS_DIR / self._TEMPLATE_OBTER_PONTOS
        resposta = base.executar(caminho_template, bypass_request_token=bypass_request_token)

        if not getattr(resposta, "ok", True):
            self._registrar_erro(
                base,
                {"metodo": "get", "url": getattr(resposta, "url", None)},
                resposta_registro=resposta,
            )
            raise RuntimeError(f"Request falhou com status {resposta.status_code}")

        corpo = resposta.json()
        if not isinstance(corpo, dict):
            return {"daily_sets": [], "more_promotions": []}

        dashboard = corpo.get("dashboard")
        if not isinstance(dashboard, dict):
            return {"daily_sets": [], "more_promotions": []}

        promocoes = []
        for item in dashboard.get("morePromotions") or []:
            if isinstance(item, dict):
                promocoes.append(self._montar_promocao(item))

        conjuntos = []
        for data_ref, itens in (dashboard.get("dailySetPromotions") or {}).items():
            if isinstance(itens, list):
                promos_data = []
                for it in itens:
                    if isinstance(it, dict):
                        promos_data.append(self._montar_promocao(it, data_ref))
                if promos_data:
                    conjuntos.append({"date": data_ref, "promotions": promos_data})

        return {
            "daily_sets": conjuntos,
            "more_promotions": promocoes,
            "raw": corpo,
            "raw_dashboard": dashboard,
        }

    def pegar_recompensas(
        self,
        base: BaseRequest,
        *,
        bypass_request_token: bool = False,
    ) -> Mapping[str, object]:
        recompensas = self.obter_recompensas(base, bypass_request_token=bypass_request_token)

        daily_sets = recompensas.get("daily_sets", []) if isinstance(recompensas, dict) else []
        more_promotions = recompensas.get("more_promotions", []) if isinstance(recompensas, dict) else []

        if not daily_sets and not more_promotions:
            return {"daily_sets": [], "more_promotions": []}

        # Criação do diretório e arquivo de template para o exemplo funcionar
        REQUESTS_DIR.mkdir(exist_ok=True)
        template_path = REQUESTS_DIR / self._TEMPLATE_EXECUTAR_TAREFA
        if not template_path.exists():
            with open(template_path, 'w', encoding="utf-8") as f:
                json.dump({"data": {}}, f)
        
        with open(template_path, encoding="utf-8") as arquivo:
            template_base = json.load(arquivo)

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
                payload["__RequestVerificationToken"] = base.token_antifalsificacao
                template["data"] = payload

                argumentos = base._montar(template, bypass_request_token=bypass_request_token)
                try:
                    resposta = base._enviar(argumentos)
                except Exception as erro:
                    self._registrar_erro(
                        base,
                        {"metodo": argumentos.get("metodo"), "url": argumentos.get("url")},
                        erro_registro=erro,
                        extras_registro={"id": identificador, "hash": hash_promocao},
                    )
                    promocoes_resultado.append(
                        {
                            "id": identificador,
                            "hash": hash_promocao,
                            "ok": False,
                            "status_code": None,
                            "erro": repr(erro),
                        }
                    )
                    continue

                if not getattr(resposta, "ok", False):
                    self._registrar_erro(
                        base,
                        {"metodo": argumentos.get("metodo"), "url": argumentos.get("url")},
                        resposta_registro=resposta,
                        extras_registro={"id": identificador, "hash": hash_promocao},
                    )

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
                # Correção: extrai a lista de promoções do dicionário retornado
                resultados_more_promotions = resultado["promotions"]

        return {
            "daily_sets": resultados_daily_sets,
            "more_promotions": resultados_more_promotions,
        }

    @staticmethod
    def _parse_bool(value: str | None) -> bool:
        if value is None:
            return False
        valor_normalizado = value.strip().lower()
        return valor_normalizado in {"1", "true", "t", "yes", "y", "on"}

    def _montar_promocao(self, item: Mapping[str, object], data_ref: str | None = None) -> Mapping[str, object]:
        atributos_obj = item.get("attributes")
        atributos = atributos_obj if isinstance(atributos_obj, dict) else {}

        pontos = self._para_int(item.get("pointProgressMax")) or self._para_int(atributos.get("max")) or self._para_int(atributos.get("link_text"))

        tipo = None
        for chave in ("type", "promotionType", "promotionSubtype"):
            valor = item.get(chave)
            if not isinstance(valor, str) and isinstance(atributos.get(chave), str):
                valor = atributos.get(chave)
            if isinstance(valor, str):
                valor_limpo = valor.strip()
                if valor_limpo:
                    tipo = valor_limpo
                    break

        completo_atributo = atributos.get("complete")
        completo = bool(item.get("complete"))
        if isinstance(completo_atributo, str) and not completo:
            completo = completo_atributo.strip().lower() == "true"

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

    @staticmethod
    def _registrar_erro(
        parametros: BaseRequest,
        chamada: Mapping[str, object],
        *,
        resposta_registro: object | None = None,
        erro_registro: BaseException | None = None,
        extras_registro: Mapping[str, object] | None = None,
    ) -> Path:
        base = Path.cwd() / "error_logs"
        base.mkdir(parents=True, exist_ok=True)
        destino = base / f"request_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        destino.mkdir(parents=True, exist_ok=True)

        detalhes = {
            "perfil": getattr(parametros, "perfil", None),
            "metodo": chamada.get("metodo"),
            "url": chamada.get("url"),
        }
        if extras_registro:
            detalhes.update(extras_registro)
        if resposta_registro is not None:
            detalhes["status"] = getattr(resposta_registro, "status_code", None)
        if erro_registro is not None:
            detalhes["erro"] = repr(erro_registro)
            detalhes["traceback"] = "\n".join(
                traceback.format_exception(type(erro_registro), erro_registro, erro_registro.__traceback__)
            )

        (destino / "detalhes.json").write_text(json.dumps(detalhes, indent=2, ensure_ascii=False), encoding="utf-8")
        return destino


__all__ = ["RewardsDataAPI"]

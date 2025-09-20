"""Camada de acesso à API do Microsoft Rewards."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import traceback
from typing import Any, Dict, Iterable, Mapping, Optional, List
from botasaurus.beep_utils import beep_input
from botasaurus_requests.response import Response

from .helpers import extract_request_verification_token
from .logging import log
from .session import GerenciadorSolicitacoesRewards, ParametrosManualSolicitacao
from .template_requester import TemplateRequester


REQUESTS_DIR = Path(__file__).resolve().parents[1] / "requests"


class APIRecompensas:
    """Agrupa chamadas autenticadas e utilitários de parsing da API."""

    _TEMPLATE_OBTER_PONTOS = "rewards_obter_pontos.json"
    _TEMPLATE_EXECUTAR_TAREFA = "pegar_recompensa_rewards.json"

    def __init__(
        self,
        gerenciador: GerenciadorSolicitacoesRewards,
        *,
        palavras_erro: Optional[Iterable[str]] = None,
    ) -> None:
        self._gerenciador = gerenciador
        self._palavras_erro = list(palavras_erro or [])
        self._parametros_cache: Optional[ParametrosManualSolicitacao] = None

    def obter_pontos(
        self,
        *,
        parametros: Optional[Mapping[str, str]] = None,
        palavras_erro: Optional[Iterable[str]] = None,
    ) -> Mapping:
        contexto = self.obter_parametros(palavras_erro)
        requester = TemplateRequester(parametros=contexto, diretorio=REQUESTS_DIR)
        chamada: Dict[str, Any] = {}
        try:
            chamada, resposta = requester.executar(
                self._TEMPLATE_OBTER_PONTOS,
                params_extra=parametros,
            )
        except Exception as erro:
            pasta = self.registrar_erro(contexto, chamada, erro_registro=erro)
            log.erro(
                "Erro ao obter pontos",
                perfil=contexto.perfil,
                url=chamada.get("url"),
                pasta=str(pasta),
                detalhe=str(erro),
            )
            raise

        if hasattr(resposta, "ok") and not resposta.ok:
            pasta = self.registrar_erro(contexto, chamada, resposta_registro=resposta)
            log.erro(
                "Resposta nao OK ao obter pontos",
                perfil=contexto.perfil,
                url=chamada["url"],
                status=resposta.status_code,
                pasta=str(pasta),
            )
            raise RuntimeError(f"Request falhou com status {resposta.status_code}")

        palavras_detectadas = self.detectar_palavras_erro(resposta, contexto.palavras_erro)
        if palavras_detectadas:
            pasta = self.registrar_erro(
                contexto,
                chamada,
                resposta_registro=resposta,
                extras_registro={"palavras_detectadas": palavras_detectadas},
            )
            log.erro(
                "Palavras de erro detectadas ao obter pontos",
                perfil=contexto.perfil,
                url=chamada["url"],
                palavras=palavras_detectadas,
                pasta=str(pasta),
            )
            raise RuntimeError(
                "Request considerado falho por conter palavras de erro: "
                + ", ".join(palavras_detectadas)
            )

        try:
            return resposta.json()
        except Exception as exc:
            log.aviso(
                "Nao foi possivel interpretar JSON de pontos",
                detalhe=str(exc),
            )
            raise

    def obter_recompensas(
        self,
        *,
        parametros: Optional[Mapping[str, str]] = None,
        palavras_erro: Optional[Iterable[str]] = None,
    ) -> Mapping:
        contexto = self.obter_parametros(palavras_erro)
        requester = TemplateRequester(parametros=contexto, diretorio=REQUESTS_DIR)
        chamada: Dict[str, Any] = {}
        try:
            chamada, resposta = requester.executar(
                self._TEMPLATE_OBTER_PONTOS,
                params_extra=parametros,
            )
        except Exception as erro:
            pasta = self.registrar_erro(contexto, chamada, erro_registro=erro)
            log.erro(
                "Erro ao obter recompensas",
                perfil=contexto.perfil,
                url=chamada.get("url"),
                pasta=str(pasta),
                detalhe=str(erro),
            )
            raise

        if hasattr(resposta, "ok") and not resposta.ok:
            pasta = self.registrar_erro(contexto, chamada, resposta_registro=resposta)
            log.erro(
                "Resposta nao OK ao obter recompensas",
                perfil=contexto.perfil,
                url=chamada["url"],
                status=resposta.status_code,
                pasta=str(pasta),
            )
            raise RuntimeError(f"Request falhou com status {resposta.status_code}")

        try:
            corpo = resposta.json()
        except Exception as exc:
            log.aviso(
                "Nao foi possivel interpretar JSON de recompensas",
                detalhe=str(exc),
            )
            raise

        if not isinstance(corpo, Mapping):
            raise ValueError("Resposta de recompensas nao possui formato de mapeamento")

        dashboard = corpo.get("dashboard") if isinstance(corpo, Mapping) else None
        if not isinstance(dashboard, Mapping):
            return {"daily_sets": [], "more_promotions": []}

        def para_int(valor: Any) -> Optional[int]:
            if isinstance(valor, (int, float)):
                return int(valor)
            if isinstance(valor, str):
                numeros = "".join(ch for ch in valor if ch.isdigit())
                if numeros:
                    try:
                        return int(numeros)
                    except ValueError:
                        return None
            return None

        def extrair_tipo_promocao(item: Mapping[str, Any], atributos: Mapping[str, Any]) -> Optional[str]:
            """Tenta extrair o tipo da promocao em diferentes campos."""

            for chave in ("type", "promotionType", "promotionSubtype"):
                valor = item.get(chave)
                if isinstance(valor, str) and valor.strip():
                    return valor.strip()
            for chave in ("type", "promotionType", "promotionSubtype"):
                valor = atributos.get(chave) if isinstance(atributos, Mapping) else None
                if isinstance(valor, str) and valor.strip():
                    return valor.strip()
            return None

        def montar_promocao(item: Mapping[str, Any], *, data_referencia: Optional[str] = None) -> Dict[str, Any]:
            atributos = item.get("attributes") if isinstance(item.get("attributes"), Mapping) else {}
            pontos = (
                para_int(item.get("pointProgressMax"))
                or para_int(atributos.get("max"))
                or para_int(atributos.get("link_text"))
            )
            completo_attr = atributos.get("complete") if isinstance(atributos, Mapping) else None
            url_destino = item.get("destinationUrl") or (atributos.get("destination") if isinstance(atributos, Mapping) else None)

            tipo = extrair_tipo_promocao(item, atributos)

            return {
                "id": item.get("name") or item.get("offerId"),
                "title": item.get("title") or (atributos.get("title") if isinstance(atributos, Mapping) else None),
                "description": item.get("description") or (atributos.get("description") if isinstance(atributos, Mapping) else None),
                "points": pontos,
                "complete": bool(item.get("complete") or (isinstance(completo_attr, str) and completo_attr.lower() == "true")),
                "url": url_destino,
                "date": data_referencia,
                "type": tipo,
            }

        mais_promocoes_bruto = dashboard.get("morePromotionsWithoutPromotionalItems")
        lista_promocoes = []
        if isinstance(mais_promocoes_bruto, list):
            for entrada in mais_promocoes_bruto:
                if isinstance(entrada, Mapping):
                    lista_promocoes.append(montar_promocao(entrada))

        conjuntos_diarios: List[Dict[str, Any]] = []
        diarias = dashboard.get("dailySetPromotions")
        if isinstance(diarias, Mapping):
            for data_referencia, itens in diarias.items():
                if not isinstance(itens, list):
                    continue
                promocoes_dia = []
                for item in itens:
                    if isinstance(item, Mapping):
                        promocoes_dia.append(montar_promocao(item, data_referencia=data_referencia))
                if promocoes_dia:
                    conjuntos_diarios.append(
                        {
                            "date": data_referencia,
                            "promotions": promocoes_dia,
                        }
                    )

        return {
            "daily_sets": conjuntos_diarios,
            "more_promotions": lista_promocoes,
            "raw": corpo,
            "raw_dashboard": dashboard,
        }

    def obter_parametros(
        self,
        palavras_erro: Optional[Iterable[str]] = None,
    ) -> ParametrosManualSolicitacao:
        """Recupera parâmetros atualizados para as requisições da API."""

        if palavras_erro is not None:
            self._palavras_erro = list(palavras_erro or [])
            self._parametros_cache = None
        if self._parametros_cache is None:
            self._parametros_cache = self._gerenciador.parametros_manuais(
                palavras_erro=self._palavras_erro,
            )
        return self._parametros_cache

    @staticmethod
    def registrar_erro(
        parametros: ParametrosManualSolicitacao,
        chamada: Mapping[str, Any],
        resposta_registro: Response | None = None,
        erro_registro: Exception | None = None,
        extras_registro: Optional[Mapping[str, Any]] = None,
    ) -> Path:
        """Registra artefatos de depuração relacionados a uma chamada."""

        base = Path.cwd() / "error_logs"
        base.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        destino = base / f"request_{timestamp}"
        contador = 1
        while destino.exists():
            contador += 1
            destino = base / f"request_{timestamp}_{contador}"
        destino.mkdir(parents=True, exist_ok=True)

        detalhes: Dict[str, Any] = {
            "perfil": parametros.perfil,
            "metodo": chamada.get("metodo"),
            "url": chamada.get("url"),
            "parametros": chamada.get("kwargs"),
            "headers_personalizados": chamada.get("headers"),
            "cookies_personalizados": chamada.get("cookies"),
        }
        if extras_registro:
            detalhes.update(dict(extras_registro))

        if resposta_registro is not None:
            detalhes.update(
                {
                    "status": getattr(resposta_registro, "status_code", None),
                    "motivo": getattr(resposta_registro, "reason", None),
                    "headers": dict(getattr(resposta_registro, "headers", {}) or {}),
                    "url_final": getattr(resposta_registro, "url", chamada.get("url")),
                }
            )

        if erro_registro is not None:
            detalhes["erro"] = repr(erro_registro)
            detalhes["traceback"] = "\n".join(
                traceback.format_exception(
                    type(erro_registro), erro_registro, erro_registro.__traceback__
                )
            )

        (destino / "detalhes.json").write_text(
            json.dumps(detalhes, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if resposta_registro is not None:
            try:
                conteudo_json = resposta_registro.json()
            except Exception:
                conteudo_json = None

            if conteudo_json is not None:
                (destino / "corpo.json").write_text(
                    json.dumps(conteudo_json, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            else:
                (destino / "corpo.txt").write_text(
                    resposta_registro.text or "",
                    encoding="utf-8",
                )

        return destino

    @staticmethod
    def detectar_palavras_erro(
        resposta: Response,
        palavras: Iterable[str],
    ) -> List[str]:
        """Retorna palavras de erro encontradas na resposta."""

        palavras_normalizadas = [palavra for palavra in palavras if palavra]
        if not palavras_normalizadas:
            return []

        try:
            texto = resposta.text or ""
        except Exception:
            texto = ""
        texto_minusculo = texto.lower()
        return [palavra for palavra in palavras_normalizadas if palavra in texto_minusculo]

    @staticmethod
    def extrair_pontos_disponiveis(dados: Mapping[str, Any]) -> Optional[int]:
        fila = deque([dados])
        visitados: set[int] = set()
        while fila:
            atual = fila.popleft()
            identificador = id(atual)
            if identificador in visitados:
                continue
            visitados.add(identificador)

            if isinstance(atual, Mapping):
                if "availablePoints" in atual:
                    valor = atual.get("availablePoints")
                    if isinstance(valor, (int, float)):
                        return int(valor)
                    if isinstance(valor, str) and valor.strip():
                        try:
                            return int(float(valor))
                        except ValueError:
                            return None
                    return None
                fila.extend(atual.values())
            elif isinstance(atual, list):
                fila.extend(atual)

        return None

    @staticmethod
    def _resolver_tipo_generico(promocao: Mapping[str, Any]) -> Optional[str]:
        """Extrai o tipo de uma promocao independente do formato original."""

        for chave in ("type", "promotionType", "promotionSubtype"):
            valor = promocao.get(chave)
            if isinstance(valor, str) and valor.strip():
                return valor.strip()

        atributos = promocao.get("attributes")
        if isinstance(atributos, Mapping):
            for chave in ("type", "promotionType", "promotionSubtype"):
                valor = atributos.get(chave)
                if isinstance(valor, str) and valor.strip():
                    return valor.strip()

        return None

    @staticmethod
    def _iterar_promocoes(dados: Any):
        """Gera promoscoes conhecendo tanto o formato bruto quanto o normalizado."""

        if not isinstance(dados, Mapping):
            return

        possui_formato_normalizado = False

        diarias = dados.get("daily_sets")
        if isinstance(diarias, list):
            possui_formato_normalizado = True
            for conjunto in diarias:
                if isinstance(conjunto, Mapping):
                    promocoes = conjunto.get("promotions")
                    if isinstance(promocoes, list):
                        for item in promocoes:
                            if isinstance(item, Mapping):
                                yield item

        mais = dados.get("more_promotions")
        if isinstance(mais, list):
            possui_formato_normalizado = True
            for item in mais:
                if isinstance(item, Mapping):
                    yield item

        if possui_formato_normalizado:
            return

        dashboard = dados.get("dashboard")
        if not isinstance(dashboard, Mapping):
            return

        diarias_bruto = dashboard.get("dailySetPromotions")
        if isinstance(diarias_bruto, Mapping):
            for itens in diarias_bruto.values():
                if isinstance(itens, list):
                    for item in itens:
                        if isinstance(item, Mapping):
                            yield item

        mais_bruto = dashboard.get("morePromotionsWithoutPromotionalItems")
        if isinstance(mais_bruto, list):
            for item in mais_bruto:
                if isinstance(item, Mapping):
                    yield item

    @classmethod
    def contar_recompensas_por_tipo(cls, dados: Any) -> Dict[str, int]:
        """Agrupa as promoscoes por tipo retornando suas contagens."""

        contagem = defaultdict(int)
        for promocao in cls._iterar_promocoes(dados) or []:
            tipo = cls._resolver_tipo_generico(promocao)
            if not tipo:
                continue
            contagem[tipo] += 1

        return dict(sorted(contagem.items()))

    @classmethod
    def contar_recompensas(cls, dados: Any) -> int:
        """Retorna o total de promoscoes encontradas no payload informado."""

        total = 0
        for _ in cls._iterar_promocoes(dados) or []:
            total += 1
        if total:
            return total

        visitados: set[int] = set()
        restante = 0

        def visitar(alvo: Any) -> None:
            nonlocal restante
            identificador = id(alvo)
            if identificador in visitados:
                return
            visitados.add(identificador)

            if isinstance(alvo, Mapping):
                preco = alvo.get("price")
                if isinstance(preco, (int, float)):
                    restante += 1
                elif isinstance(preco, str):
                    texto = preco.replace(".", "", 1)
                    if texto.isdigit():
                        restante += 1
                for valor in alvo.values():
                    visitar(valor)
            elif isinstance(alvo, list):
                for valor in alvo:
                    visitar(valor)

        visitar(dados)
        return restante

    def _resolver_token_tarefas(self) -> Optional[str]:
        """Obtém o token antifalsificação atual usando os helpers configurados."""

        driver = getattr(self._gerenciador, "driver", None)
        if driver is not None:
            try:
                html_atual = getattr(driver, "page_source", None)
            except Exception as exc:  # pragma: no cover - depende do driver real
                log.debug("Falha ao ler HTML para token", detalhe=str(exc))
                html_atual = None
            token_html = extract_request_verification_token(html_atual)
            if token_html:
                return token_html

        sessao = self._gerenciador.dados_sessao
        if sessao and sessao.request_verification_token:
            return sessao.request_verification_token

        if self._parametros_cache and self._parametros_cache.verification_token:
            return self._parametros_cache.verification_token

        return None

    def executar_tarefas(
        self,
        dados_recompensas: Mapping[str, Any],
        *,
        registro: Any | None = None,
    ) -> Dict[str, int]:
        """Executa as tarefas pendentes reportando seu status."""

        logger = registro or log
        resumo: Dict[str, int] = {
            "executadas": 0,
            "falhas": 0,
            "ignoradas": 0,
            "ja_concluidas": 0,
            "total": 0,
        }

        if not isinstance(dados_recompensas, Mapping):
            return resumo

        base_iteracao: Any = dados_recompensas.get("raw") if isinstance(dados_recompensas, Mapping) else None
        if not isinstance(base_iteracao, Mapping):
            base_iteracao = dados_recompensas

        tarefas: List[Dict[str, Any]] = []
        vistos: set[tuple[str, str]] = set()

        for promocao in self._iterar_promocoes(base_iteracao) or []:
            if not isinstance(promocao, Mapping):
                continue

            if bool(promocao.get("complete")):
                resumo["ja_concluidas"] += 1
                continue

            identificador = (
                promocao.get("offerId")
                or promocao.get("id")
                or promocao.get("name")
            )
            atributos = promocao.get("attributes") if isinstance(promocao.get("attributes"), Mapping) else None
            hash_valor = promocao.get("hash")
            if not hash_valor and isinstance(atributos, Mapping):
                hash_valor = atributos.get("hash")

            if not identificador or not hash_valor:
                resumo["ignoradas"] += 1
                logger.debug(
                    "Tarefa ignorada por falta de dados",
                    id=identificador,
                    possui_hash=bool(hash_valor),
                )
                continue

            chave = (str(identificador), str(hash_valor))
            if chave in vistos:
                continue
            vistos.add(chave)

            tipo = self._resolver_tipo_generico(promocao) or ""
            form_val = None
            if isinstance(atributos, Mapping):
                form_val = atributos.get("form") or atributos.get("Form")

            tarefas.append(
                {
                    "id": str(identificador),
                    "hash": str(hash_valor),
                    "type": tipo,
                    "form": form_val,
                }
            )

        token = self._resolver_token_tarefas() or None
        parametros = self.obter_parametros()
        if token or parametros.verification_token:
            token_final = token or parametros.verification_token
            if token_final != parametros.verification_token:
                parametros = replace(parametros, verification_token=token_final)
        else:
            token_final = None

        if tarefas and not token_final:
            resumo["ignoradas"] += len(tarefas)
            resumo["total"] = (
                resumo["executadas"]
                + resumo["falhas"]
                + resumo["ja_concluidas"]
                + resumo["ignoradas"]
            )
            logger.aviso("Token de verificacao ausente; tarefas nao executadas", pendentes=len(tarefas))
            return resumo

        requester = TemplateRequester(parametros=parametros, diretorio=REQUESTS_DIR)

        for tarefa in tarefas:
            data_extra = {
                "id": tarefa["id"],
                "hash": tarefa["hash"],
            }
            if tarefa["type"]:
                data_extra["type"] = tarefa["type"]
            if tarefa["form"]:
                data_extra["form"] = tarefa["form"]

            try:
                _, resposta = requester.executar(
                    self._TEMPLATE_EXECUTAR_TAREFA,
                    data_extra=data_extra,
                )
            except Exception as exc:
                resumo["falhas"] += 1
                logger.erro(
                    "Execucao de tarefa falhou",
                    id=tarefa["id"],
                    tipo=tarefa["type"] or "desconhecido",
                    detalhe=str(exc),
                )
                continue

            corpo = None
            try:
                corpo = resposta.json()
            except Exception:
                corpo = None

            sucesso = False
            if corpo is not None:
                status_valor = str(corpo.get("status", "")).lower()
                sucesso = bool(
                    corpo.get("success")
                    or corpo.get("isSuccess")
                    or status_valor in {"success", "sucesso", "ok", "completed", "complete"}
                )
            elif getattr(resposta, "ok", False):
                sucesso = True

            if sucesso:
                resumo["executadas"] += 1
                logger.sucesso(
                    "Tarefa executada",
                    id=tarefa["id"],
                    tipo=tarefa["type"] or "desconhecido",
                )
            else:
                resumo["falhas"] += 1
                logger.aviso(
                    "Tarefa com resposta inesperada",
                    id=tarefa["id"],
                    tipo=tarefa["type"] or "desconhecido",
                    status=getattr(resposta, "status_code", None),
                )

        resumo["total"] = (
            resumo["executadas"]
            + resumo["falhas"]
            + resumo["ja_concluidas"]
            + resumo["ignoradas"]
        )
        return resumo


__all__ = ["APIRecompensas"]

"""API para conduzir pesquisas no Bing utilizando templates preexistentes."""

from __future__ import annotations

import json
import random
import re
from copy import deepcopy
from pathlib import Path
from typing import Callable, Mapping, MutableMapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from flask import Blueprint, Response, current_app, jsonify, request
from flask.views import MethodView
from wonderwords import RandomWord

from services.session_service import BaseRequest

REQUESTS_DIR = Path(__file__).resolve().parents[1] / "requests"
_TEMPLATE_PESQUISA_BING = "pesquisa_bing.json"
_ERRO_PADRAO = ("captcha", "temporarily unavailable", "error")

_CONSULTAS_DINAMICAS: tuple[str, ...] = (
    "comprehensive analysis of {adj1} {noun1} adoption in {noun2}",
    "case studies comparing {adj1} {noun1} with {adj2} {noun2}",
    "strategies to {verb1} {adj1} {noun1} for {noun2} growth",
    "innovation roadmap for {adj1} {noun1} within {adj2} {noun2} ecosystems",
    "economic impact of {noun1} on {adj1} {noun2} initiatives",
    "forecast of {adj1} {noun1} and emerging {noun2} opportunities",
    "advanced research topics combining {adj1} {noun1} and {adj2} {noun2}",
    "best practices to {verb1} {noun1} across {adj1} {noun2} projects",
)


_PLACEHOLDER_PATTERN = re.compile(r"{([a-zA-Z0-9_]+)}")


class _GeradorConsultas:
    """Gera consultas em inglês recheadas de termos aleatórios via Wonderwords."""

    def __init__(
        self,
        consultas_dinamicas: Sequence[str] | None = None,
        random_word: RandomWord | None = None,
    ) -> None:
        self._consultas_dinamicas = tuple(consultas_dinamicas or _CONSULTAS_DINAMICAS)
        self._random_word = random_word or RandomWord()

    def gerar(self) -> str:
        consulta_dinamica = self._consulta_dinamica()
        if consulta_dinamica:
            return consulta_dinamica
        return self._fallback()

    def _consulta_dinamica(self) -> str | None:
        if not self._consultas_dinamicas:
            return None

        molde = random.choice(self._consultas_dinamicas)
        placeholders = set(_PLACEHOLDER_PATTERN.findall(molde))
        if not placeholders:
            return None

        usados: set[str] = set()
        valores: dict[str, str] = {}
        for placeholder in placeholders:
            base = self._resolver_base_placeholder(placeholder)
            palavra = self._gerar_palavra(base, usados)
            if not palavra:
                return None
            valores[placeholder] = palavra
            usados.add(palavra)

        try:
            return molde.format(**valores)
        except KeyError:
            return None

    def _fallback(self) -> str:
        palavras: list[str] = []
        usados: set[str] = set()
        for base in ("adj", "noun", "noun", "verb"):
            palavra = self._gerar_palavra(base, usados)
            if palavra:
                palavras.append(palavra)
                usados.add(palavra)

        if not palavras:
            return "global insights on technology developments"

        frase = "strategic perspective on " + " ".join(palavras)
        return frase

    @staticmethod
    def _resolver_base_placeholder(placeholder: str) -> str:
        return placeholder.rstrip("0123456789") or placeholder

    def _gerar_palavra(self, base: str, usados: set[str]) -> str | None:
        categorias = self._categorias_para_base(base)
        if not categorias:
            return None

        for _ in range(8):
            try:
                palavra = self._random_word.word(
                    include_categories=categorias,
                    word_min_length=4,
                    exclude_with_spaces=True,
                )
            except Exception:
                palavra = None

            if not palavra:
                continue

            palavra = palavra.lower()
            if palavra in usados or not palavra.isalpha():
                continue
            return palavra

        return None

    @staticmethod
    def _categorias_para_base(base: str) -> Sequence[str] | None:
        if base == "noun":
            return ("nouns",)
        if base == "adj":
            return ("adjectives",)
        if base == "verb":
            return ("verbs",)
        return None


# Endpoint principal da API de pesquisa
class _BingSearchView(MethodView):
    """View Flask responsável por iniciar pesquisas no Bing."""

    def __init__(self, api: "BingSearchAPI") -> None:
        self._api = api

    def post(self) -> Response:  # pragma: no cover - exercitado em testes específicos
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, Mapping):
            return self._api._json_error("Corpo JSON deve ser um objeto.", 400)

        consulta = payload.get("query")
        consulta = consulta if isinstance(consulta, str) and consulta.strip() else None

        try:
            resultado = self._api.pesquisar(query=consulta)
        except LookupError as exc:
            return self._api._json_error(str(exc), 503)
        except Exception:  # pragma: no cover - logging auxiliar
            logger = getattr(current_app, "logger", None)
            if logger:
                logger.exception("Falha ao realizar pesquisa no Bing")
            return self._api._json_error("Erro interno ao realizar pesquisa.", 500)

        return jsonify(resultado)


class BingSearchAPI:
    """Executa pesquisas HTTP no Bing com base em templates."""

    def __init__(
        self,
        request_provider: Callable[[], BaseRequest] | None = None,
        *,
        gerador_consultas: _GeradorConsultas | None = None,
        palavras_erro: Sequence[str] | None = None,
    ) -> None:
        self._request_provider = request_provider
        self._gerador = gerador_consultas or _GeradorConsultas()
        self._palavras_erro = tuple(palavra.lower() for palavra in (palavras_erro or _ERRO_PADRAO))
        self._blueprint = Blueprint("bing_search", __name__)
        view = _BingSearchView.as_view("bing_search", api=self)
        self._blueprint.add_url_rule("/bing/search", view_func=view, methods=["POST"])

    @property
    def blueprint(self) -> Blueprint:
        return self._blueprint

    def set_request_provider(self, provider: Callable[[], BaseRequest]) -> None:
        """Define o provider padrão utilizado pelas rotas Flask."""

        self._request_provider = provider

    def pesquisar(
        self,
        *,
        base: BaseRequest | None = None,
        query: str | None = None,
    ) -> Mapping[str, object]:
        requisicao_base = base or self._base_request_from_provider()
        consulta = query.strip() if isinstance(query, str) and query.strip() else self._gerador.gerar()

        template = self._carregar_template()
        template_personalizado = self._aplicar_consulta(template, consulta)

        argumentos = requisicao_base._montar(template_personalizado, False)  # type: ignore[attr-defined]
        resposta = requisicao_base._enviar(argumentos)  # type: ignore[attr-defined]
        self._validar_resposta(resposta)
        return self._resumo_resposta(consulta, argumentos, resposta)

    def _base_request_from_provider(self) -> BaseRequest:
        if not self._request_provider:
            raise LookupError("Provider de requisições não configurado.")
        requisicao = self._request_provider()
        if not isinstance(requisicao, BaseRequest):
            raise LookupError("Provider retornou objeto inválido para requisições.")
        return requisicao

    def _carregar_template(self) -> MutableMapping[str, object]:
        caminho = REQUESTS_DIR / _TEMPLATE_PESQUISA_BING
        with caminho.open("r", encoding="utf-8") as arquivo:
            return json.load(arquivo)

    def _aplicar_consulta(
        self,
        template: MutableMapping[str, object],
        consulta: str,
    ) -> MutableMapping[str, object]:
        resultado = deepcopy(template)

        url = resultado.get("url")
        if isinstance(url, str):
            resultado["url"] = self._atualizar_pesquisa(url, consulta)

        headers = resultado.get("headers")
        if isinstance(headers, MutableMapping):
            referer = headers.get("Referer")
            if isinstance(referer, str):
                headers["Referer"] = self._atualizar_pesquisa(referer, consulta)
            resultado["headers"] = dict(headers)

        data = resultado.get("data")
        if isinstance(data, MutableMapping):
            destino = data.get("url")
            if isinstance(destino, str):
                data["url"] = self._atualizar_pesquisa(destino, consulta)
            resultado["data"] = dict(data)

        return resultado

    @staticmethod
    def _atualizar_pesquisa(url: str, consulta: str) -> str:
        analise = urlparse(url)
        parametros = list(parse_qsl(analise.query, keep_blank_values=True))

        chaves_atualizadas = set()
        for indice, (chave, valor) in enumerate(parametros):
            if chave in {"q", "pq"}:
                parametros[indice] = (chave, consulta)
                chaves_atualizadas.add(chave)

        for chave in ("q", "pq"):
            if chave not in chaves_atualizadas:
                parametros.append((chave, consulta))

        nova_query = urlencode(parametros, doseq=True)
        return urlunparse(analise._replace(query=nova_query))

    def _validar_resposta(self, resposta) -> None:
        if resposta is None:
            raise RuntimeError("Resposta vazia ao consultar o Bing.")

        status = getattr(resposta, "status_code", None)
        if status and status >= 400:
            raise RuntimeError(f"Bing respondeu com status inválido: {status}")

        texto = getattr(resposta, "text", "")
        if not texto:
            raise RuntimeError("Bing retornou resposta sem corpo.")

        texto_lower = texto.lower()
        for palavra in self._palavras_erro:
            if palavra and palavra in texto_lower:
                raise RuntimeError(f"Resposta contém termo de erro: {palavra}")

    @staticmethod
    def _resumo_resposta(consulta: str, argumentos: Mapping[str, object], resposta) -> Mapping[str, object]:
        resumo_requisicao: dict[str, object] = {
            "method": argumentos.get("metodo"),
            "url": argumentos.get("url"),
        }

        headers = argumentos.get("headers")
        if isinstance(headers, Mapping) and headers.get("Referer"):
            resumo_requisicao["referer"] = headers["Referer"]

        data = argumentos.get("data")
        if isinstance(data, Mapping) and data.get("url"):
            resumo_requisicao["data_url"] = data["url"]

        resumo_resposta: dict[str, object] = {
            "status": getattr(resposta, "status_code", None),
            "final_url": getattr(resposta, "url", None),
        }

        elapsed = getattr(resposta, "elapsed", None)
        if elapsed is not None:
            try:
                resumo_resposta["elapsed_seconds"] = elapsed.total_seconds()
            except Exception:
                pass

        return {
            "query": consulta,
            "request": resumo_requisicao,
            "response": resumo_resposta,
        }

    @staticmethod
    def _json_error(message: str, status_code: int) -> Response:
        resposta = jsonify({"error": {"message": message}})
        resposta.status_code = status_code
        return resposta


__all__ = ["BingSearchAPI"]

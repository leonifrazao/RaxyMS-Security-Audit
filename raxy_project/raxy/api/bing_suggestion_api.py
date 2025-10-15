"""API para obter sugestões de pesquisa do Bing utilizando templates com SessionManagerService."""

from __future__ import annotations

import json
import random
from copy import deepcopy
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from raxy.interfaces.services import IBingSuggestion
from raxy.core.session_manager_service import SessionManagerService

REQUESTS_DIR = Path(__file__).resolve().parent / "requests_templates"
_TEMPLATE_SUGGESTION_BING = "suggestion_search.json"
_ERRO_PADRAO = ("captcha", "temporarily unavailable", "error")


class BingSuggestionAPI(IBingSuggestion):
    def __init__(self, *, palavras_erro: Sequence[str] | None = None) -> None:
        self._palavras_erro = tuple(palavra.lower() for palavra in (palavras_erro or _ERRO_PADRAO))

    def get_all(self, sessao: SessionManagerService, keyword: str) -> list[dict[str, Any]]:
        if not isinstance(keyword, str) or not keyword.strip():
            raise ValueError("A palavra-chave não pode ser vazia.")

        template = self._carregar_template()
        template_personalizado = self._aplicar_consulta(template, keyword.strip())
        resposta = sessao.execute_template(template_personalizado, bypass_request_token=False)

        texto = getattr(resposta, "text", "")
        if not texto:
            raise RuntimeError("Bing retornou resposta sem corpo.")

        texto_lower = texto.lower()
        for palavra in self._palavras_erro:
            if palavra and palavra in texto_lower:
                raise RuntimeError(f"Resposta contém termo de erro: {palavra}")

        try:
            dados = resposta.json()
        except json.JSONDecodeError as e:
            raise RuntimeError("Falha ao decodificar a resposta JSON do Bing.") from e

        suggestions = dados.get("s")
        if not isinstance(suggestions, list):
            raise TypeError("A resposta da API de sugestões não continha uma lista válida.")
        return suggestions

    def get_random(self, sessao: SessionManagerService, keyword: str) -> dict[str, Any]:
        all_suggestions = self.get_all(sessao, keyword)
        if not all_suggestions:
            raise ValueError(f"Nenhuma sugestão encontrada para a palavra-chave: {keyword}")
        return random.choice(all_suggestions)

    def _carregar_template(self) -> dict[str, object]:
        caminho = REQUESTS_DIR / _TEMPLATE_SUGGESTION_BING
        with caminho.open("r", encoding="utf-8") as arquivo:
            return json.load(arquivo)

    def _aplicar_consulta(self, template: dict[str, object], consulta: str) -> dict[str, object]:
        resultado = deepcopy(template)
        url = resultado.get("url")
        if isinstance(url, str):
            resultado["url"] = self._atualizar_url_com_consulta(url, consulta)
        return resultado

    @staticmethod
    def _atualizar_url_com_consulta(url: str, consulta: str) -> str:
        analise = urlparse(url)
        parametros = list(parse_qsl(analise.query, keep_blank_values=True))
        chave_atualizada = False
        for indice, (chave, _) in enumerate(parametros):
            if chave == "qry":
                parametros[indice] = (chave, consulta)
                chave_atualizada = True
                break
        if not chave_atualizada:
            parametros.append(("qry", consulta))
        nova_query = urlencode(parametros, doseq=True)
        return urlunparse(analise._replace(query=nova_query))

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
from raxy.core.exceptions import (
    BingAPIException,
    InvalidAPIResponseException,
    JSONParsingException,
    InvalidInputException,
    wrap_exception,
)

REQUESTS_DIR = Path(__file__).resolve().parent / "requests_templates"
_TEMPLATE_SUGGESTION_BING = "suggestion_search.json"
_ERRO_PADRAO = ("captcha", "temporarily unavailable", "error")


class BingSuggestionAPI(IBingSuggestion):
    def __init__(self, *, palavras_erro: Sequence[str] | None = None) -> None:
        self._palavras_erro = tuple(palavra.lower() for palavra in (palavras_erro or _ERRO_PADRAO))

    def get_all(self, sessao: SessionManagerService, keyword: str) -> list[dict[str, Any]]:
        """Obtém todas as sugestões do Bing com tratamento robusto de erros."""
        if not isinstance(keyword, str) or not keyword.strip():
            raise InvalidInputException(
                "A palavra-chave não pode ser vazia.",
                details={"keyword": keyword, "type": type(keyword).__name__}
            )

        try:
            template = self._carregar_template()
        except Exception as e:
            raise wrap_exception(
                e, BingAPIException,
                "Erro ao carregar template de sugestões"
            )
        
        try:
            template_personalizado = self._aplicar_consulta(template, keyword.strip())
        except Exception as e:
            raise wrap_exception(
                e, BingAPIException,
                "Erro ao aplicar consulta ao template",
                keyword=keyword
            )
        
        try:
            resposta = sessao.execute_template(template_personalizado, bypass_request_token=False)
        except Exception as e:
            raise wrap_exception(
                e, BingAPIException,
                "Erro ao executar requisição de sugestões",
                keyword=keyword
            )

        texto = getattr(resposta, "text", "")
        if not texto:
            raise InvalidAPIResponseException(
                "Bing retornou resposta sem corpo.",
                details={"status_code": getattr(resposta, "status_code", None), "keyword": keyword}
            )

        texto_lower = texto.lower()
        for palavra in self._palavras_erro:
            if palavra and palavra in texto_lower:
                raise BingAPIException(
                    f"Resposta contém termo de erro: {palavra}",
                    details={"keyword": keyword, "error_term": palavra, "response_preview": texto[:200]}
                )

        try:
            dados = resposta.json()
        except json.JSONDecodeError as e:
            raise wrap_exception(
                e, JSONParsingException,
                "Falha ao decodificar a resposta JSON do Bing.",
                keyword=keyword, response_preview=texto[:200]
            )

        suggestions = dados.get("s")
        if not isinstance(suggestions, list):
            raise InvalidAPIResponseException(
                "A resposta da API de sugestões não continha uma lista válida.",
                details={"keyword": keyword, "response_type": type(suggestions).__name__, "response_keys": list(dados.keys()) if isinstance(dados, dict) else None}
            )
        return suggestions

    def get_random(self, sessao: SessionManagerService, keyword: str) -> dict[str, Any]:
        """Obtém uma sugestão aleatória com tratamento de erros."""
        try:
            all_suggestions = self.get_all(sessao, keyword)
        except BingAPIException:
            raise
        except Exception as e:
            raise wrap_exception(
                e, BingAPIException,
                "Erro ao obter sugestões para seleção aleatória",
                keyword=keyword
            )
        
        if not all_suggestions:
            raise BingAPIException(
                f"Nenhuma sugestão encontrada para a palavra-chave: {keyword}",
                details={"keyword": keyword}
            )
        return random.choice(all_suggestions)

    def _carregar_template(self) -> dict[str, object]:
        """Carrega o template de sugestões com tratamento de erros."""
        caminho = REQUESTS_DIR / _TEMPLATE_SUGGESTION_BING
        try:
            with caminho.open("r", encoding="utf-8") as arquivo:
                return json.load(arquivo)
        except FileNotFoundError as e:
            raise wrap_exception(
                e, BingAPIException,
                "Template de sugestões não encontrado",
                template_path=str(caminho)
            )
        except json.JSONDecodeError as e:
            raise wrap_exception(
                e, JSONParsingException,
                "Template de sugestões contém JSON inválido",
                template_path=str(caminho)
            )
        except Exception as e:
            raise wrap_exception(
                e, BingAPIException,
                "Erro ao abrir template de sugestões",
                template_path=str(caminho)
            )

    def _aplicar_consulta(self, template: dict[str, object], consulta: str) -> dict[str, object]:
        """Aplica a consulta ao template com tratamento de erros."""
        try:
            resultado = deepcopy(template)
            url = resultado.get("url")
            if isinstance(url, str):
                resultado["url"] = self._atualizar_url_com_consulta(url, consulta)
            return resultado
        except Exception as e:
            raise wrap_exception(
                e, BingAPIException,
                "Erro ao aplicar consulta ao template",
                consulta=consulta
            )

    @staticmethod
    def _atualizar_url_com_consulta(url: str, consulta: str) -> str:
        """Atualiza a URL com a consulta fornecida."""
        try:
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
        except Exception as e:
            # Se falhar, retorna URL original
            return url

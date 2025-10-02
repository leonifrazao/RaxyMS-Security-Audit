"""API para obter sugestões de pesquisa do Bing utilizando templates."""

from __future__ import annotations

import json
import random
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, MutableMapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Supondo que o serviço de sessão esteja acessível a partir daqui
# Ajuste o import se sua estrutura for diferente
from services.session_service import BaseRequest

# Caminho corrigido com base na estrutura de pastas fornecida
REQUESTS_DIR = Path(__file__).resolve().parent / "requests_templates"
_TEMPLATE_SUGGESTION_BING = "suggestion_search.json"
_ERRO_PADRAO = ("captcha", "temporarily unavailable", "error")


class BingSuggestionAPI:
    """Executa buscas por sugestões no Bing com base em templates."""

    def __init__(
        self,
        request_provider: Callable[[], BaseRequest],
        *,
        palavras_erro: Sequence[str] | None = None,
    ) -> None:
        """
        Inicializa a API de sugestões.
        
        Args:
            request_provider: Uma função que retorna uma instância de BaseRequest.
            palavras_erro: Uma sequência de strings que indicam erro na resposta.
        """
        self._request_provider = request_provider
        self._palavras_erro = tuple(palavra.lower() for palavra in (palavras_erro or _ERRO_PADRAO))

    def get_all(self, keyword: str) -> list[dict[str, Any]]:
        """
        Busca todas as sugestões de pesquisa para uma determinada palavra-chave.

        Args:
            keyword: O termo a ser pesquisado.

        Returns:
            Uma lista de dicionários, onde cada um representa uma sugestão.
        
        Raises:
            ValueError: Se a palavra-chave for inválida.
            TypeError: Se a resposta da API não tiver o formato esperado.
        """
        if not isinstance(keyword, str) or not keyword.strip():
            raise ValueError("A palavra-chave não pode ser vazia.")

        response_data = self._executar_requisicao(keyword.strip())
        
        # O JSON de resposta contém uma chave "s" com a lista de sugestões
        suggestions = response_data.get("s")

        if not isinstance(suggestions, list):
            raise TypeError("A resposta da API de sugestões não continha uma lista válida.")

        return suggestions

    def get_random(self, keyword: str) -> dict[str, Any]:
        """
        Busca uma sugestão de pesquisa aleatória para a palavra-chave.

        Args:
            keyword: O termo a ser pesquisado.

        Returns:
            Um dicionário representando uma única sugestão aleatória.

        Raises:
            ValueError: Se nenhuma sugestão for encontrada.
        """
        all_suggestions = self.get_all(keyword)
        if not all_suggestions:
            raise ValueError(f"Nenhuma sugestão encontrada para a palavra-chave: {keyword}")
        return random.choice(all_suggestions)

    def _executar_requisicao(self, keyword: str) -> dict[str, Any]:
        """Método central para preparar, enviar e validar a requisição."""
        requisicao_base = self._base_request_from_provider()
        template = self._carregar_template()
        template_personalizado = self._aplicar_consulta(template, keyword)

        # Assumindo que a sua classe BaseRequest tem os métodos _montar e _enviar
        argumentos = requisicao_base._montar(template_personalizado, False)  # type: ignore[attr-defined]
        resposta = requisicao_base._enviar(argumentos)  # type: ignore[attr-defined]
        
        self._validar_resposta(resposta)

        try:
            return resposta.json()
        except json.JSONDecodeError as e:
            raise RuntimeError("Falha ao decodificar a resposta JSON do Bing.") from e

    def _base_request_from_provider(self) -> BaseRequest:
        """Obtém uma instância de BaseRequest a partir do provider configurado."""
        if not self._request_provider:
            raise LookupError("Provider de requisições não configurado.")
        requisicao = self._request_provider()
        if not isinstance(requisicao, BaseRequest):
            raise LookupError("Provider retornou objeto inválido para requisições.")
        return requisicao

    def _carregar_template(self) -> MutableMapping[str, object]:
        """Carrega o arquivo de template JSON para a requisição."""
        caminho = REQUESTS_DIR / _TEMPLATE_SUGGESTION_BING
        with caminho.open("r", encoding="utf-8") as arquivo:
            return json.load(arquivo)

    def _aplicar_consulta(
        self,
        template: MutableMapping[str, object],
        consulta: str,
    ) -> MutableMapping[str, object]:
        """Aplica a consulta (palavra-chave) ao URL do template."""
        resultado = deepcopy(template)
        url = resultado.get("url")
        if isinstance(url, str):
            resultado["url"] = self._atualizar_url_com_consulta(url, consulta)
        return resultado

    @staticmethod
    def _atualizar_url_com_consulta(url: str, consulta: str) -> str:
        """Atualiza o parâmetro 'qry' no URL com a consulta fornecida."""
        analise = urlparse(url)
        parametros = list(parse_qsl(analise.query, keep_blank_values=True))

        chave_atualizada = False
        # A API de sugestões usa o parâmetro 'qry'
        for indice, (chave, _) in enumerate(parametros):
            if chave == "qry":
                parametros[indice] = (chave, consulta)
                chave_atualizada = True
                break

        if not chave_atualizada:
            parametros.append(("qry", consulta))

        nova_query = urlencode(parametros, doseq=True)
        return urlunparse(analise._replace(query=nova_query))

    def _validar_resposta(self, resposta: Any) -> None:
        """Verifica se a resposta HTTP é válida."""
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

__all__ = ["BingSuggestionAPI"]

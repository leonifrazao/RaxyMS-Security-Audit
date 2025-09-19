"""Utilitário simples para montar e enviar requests a partir de templates JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional
from urllib.parse import urljoin

from botasaurus.request import Request, request
from botasaurus_requests.response import Response

from .helpers import inject_request_verification_token
from .session import ParametrosManualSolicitacao


@request(cache=False, raise_exception=True, create_error_logs=False, output=None)
def _enviar_request(req: Request, pacote: Mapping[str, Any]) -> Response:
    metodo = str(pacote.get("metodo", "")).lower()
    operacao = getattr(req, metodo)
    url = str(pacote.get("url"))

    argumentos: Dict[str, Any] = {}
    for campo in ("params", "data", "json", "headers", "cookies", "timeout", "allow_redirects"):
        valor = pacote.get(campo)
        if valor is not None:
            argumentos[campo] = valor

    user_agent = pacote.get("user_agent")
    if user_agent is not None:
        argumentos["user_agent"] = user_agent

    return operacao(url, **argumentos)


class TemplateRequester:
    """Carrega templates HTTP e executa chamadas usando o cliente Botasaurus."""

    def __init__(self, *, parametros: ParametrosManualSolicitacao, diretorio: Path) -> None:
        self._parametros = parametros
        self._diretorio = diretorio

    def executar(
        self,
        nome_template: str,
        *,
        params_extra: Optional[Mapping[str, Any]] = None,
        data_extra: Optional[Mapping[str, Any]] = None,
        json_extra: Optional[Mapping[str, Any]] = None,
    ) -> tuple[Dict[str, Any], Response]:
        template = self._carregar(nome_template)
        requisicao = self._montar(template, params_extra, data_extra, json_extra)
        resposta = _enviar_request(requisicao)
        return requisicao, resposta

    def _carregar(self, nome: str) -> Dict[str, Any]:
        caminho = self._diretorio / nome
        conteudo = caminho.read_text(encoding="utf-8")
        return json.loads(conteudo)

    def _montar(
        self,
        template: Mapping[str, Any],
        params_extra: Optional[Mapping[str, Any]],
        data_extra: Optional[Mapping[str, Any]],
        json_extra: Optional[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        metodo = str(template.get("method", "GET")).upper()

        url_template = template.get("url")
        if url_template:
            url = str(url_template)
        else:
            destino = str(template.get("path", ""))
            url = urljoin(f"{self._parametros.url_base.rstrip('/')}/", destino.lstrip("/"))

        headers = dict(self._parametros.headers)
        headers.update(template.get("headers", {}) or {})

        cookies = dict(self._parametros.cookies)
        cookies.update(template.get("cookies", {}) or {})

        params_payload = dict(template.get("params", {}) or {})
        if params_extra:
            params_payload.update(params_extra)

        data_payload = template.get("data")
        if data_extra:
            base = data_payload if isinstance(data_payload, Mapping) else {}
            atualizado = dict(base)
            atualizado.update(data_extra)
            data_payload = atualizado

        json_payload = template.get("json")
        if json_extra:
            base = json_payload if isinstance(json_payload, Mapping) else {}
            atualizado = dict(base)
            atualizado.update(json_extra)
            json_payload = atualizado

        payload = {
            "params": params_payload or None,
            "data": data_payload,
            "json": json_payload,
        }

        payload, headers_ajustados = inject_request_verification_token(
            metodo,
            payload,
            headers,
            self._parametros.verification_token,
        )

        parametros_envio = {
            "params": payload.get("params"),
            "data": payload.get("data"),
            "json": payload.get("json"),
            "headers": headers_ajustados,
            "cookies": cookies,
            "user_agent": self._parametros.user_agent,
        }

        return {
            "metodo": metodo,
            "url": url,
            **parametros_envio,
            "kwargs": parametros_envio,
        }


__all__ = ["TemplateRequester"]

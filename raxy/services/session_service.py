# base_request.py

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, TYPE_CHECKING
from urllib.parse import urljoin

from botasaurus.request import Request, request
from botasaurus.soupify import soupify

if TYPE_CHECKING:  # pragma: no cover
    from raxy.domain import Conta


@dataclass(slots=True)
class ParametrosManualSolicitacao:
    """Agrupa parâmetros necessários para uma chamada manual de API."""

    perfil: str
    url_base: str
    user_agent: str
    headers: Mapping[str, str] = field(default_factory=dict)
    cookies: Mapping[str, str] = field(default_factory=dict)
    verification_token: str | None = None
    palavras_erro: tuple[str, ...] = ()
    interativo: bool = False


@dataclass(slots=True)
class SessaoSolicitacoes:
    """Representa uma sessão autenticada pronta para requests manuais."""

    conta: "Conta"
    base_request: "BaseRequest"

    @property
    def perfil(self) -> str:
        return getattr(self.base_request, "perfil", self.conta.id_perfil or self.conta.email)

    @property
    def user_agent(self) -> str:
        return getattr(self.base_request, "user_agent", "")

    @property
    def cookies(self) -> Mapping[str, str]:
        return getattr(self.base_request, "cookies", {})

    @property
    def verification_token(self) -> str | None:
        return getattr(self.base_request, "token_antifalsificacao", None)

    def parametros_manuais(
        self,
        *,
        url_base: str | None = None,
        headers: Mapping[str, str] | None = None,
        cookies: Mapping[str, str] | None = None,
        palavras_erro: tuple[str, ...] | None = None,
        interativo: bool | None = None,
    ) -> ParametrosManualSolicitacao:
        return ParametrosManualSolicitacao(
            perfil=self.perfil,
            url_base=url_base or getattr(self.base_request, "url_base", "https://rewards.bing.com/"),
            user_agent=self.user_agent,
            headers=headers or {},
            cookies=cookies or dict(self.cookies),
            verification_token=self.verification_token,
            palavras_erro=palavras_erro or (),
            interativo=bool(interativo),
        )


def _extract_request_verification_token(html):
    if not html:
        return None
    try:
        soup = soupify(html)
        campo = soup.find("input", {"name": "__RequestVerificationToken"})
        if campo and campo.get("value"):
            return campo["value"].strip() or None
    except Exception:
        return None
    return None


class BaseRequest:
    """Carrega templates JSON e executa requests autenticadas."""

    def __init__(self, perfil, driver, url_base="https://rewards.bing.com/"):
        self.perfil = perfil
        self.driver = driver
        self.url_base = url_base

        self.cookies = self.driver.get_cookies_dict()
        self.user_agent = self.driver.profile.get("UA")

        try:
            html = driver.requests.get(url_base).text
        except Exception:
            html = None
        self.token_antifalsificacao = _extract_request_verification_token(html)

    def executar(self, diretorio_template, bypass_request_token=False, use_ua = True, use_cookies = True):
        if not isinstance(diretorio_template, dict):  
            template = self._carregar(diretorio_template)
        else:
            template = diretorio_template
        args = self._montar(template, bypass_request_token, use_ua, use_cookies)
        return self._enviar(args)

    def _carregar(self, diretorio_template):
        caminho = diretorio_template
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)

    def _montar(self, template, bypass_request_token, use_ua=True, use_cookies=True):
        metodo = str(template.get("method", "GET")).upper()

        # URL
        if "url" in template:
            url = str(template["url"])
        else:
            destino = str(template.get("path", ""))
            url = urljoin(self.url_base.rstrip("/") + "/", destino.lstrip("/"))

        # headers
        headers = dict(template.get("headers") or {})
        if use_ua:
            headers.setdefault("User-Agent", self.user_agent)

        # cookies
        cookies = {}
        if use_cookies:
            cookies = dict(self.cookies)
            cookies.update(template.get("cookies") or {})

        params = template.get("params")
        data = template.get("data")
        json_payload = template.get("json")

        # injeta token se necessário
        if (
            not bypass_request_token
            and self.token_antifalsificacao
            and metodo in {"POST", "PUT", "PATCH", "DELETE"}
        ):
            if isinstance(data, dict) and not data.get("__RequestVerificationToken"):
                data["__RequestVerificationToken"] = self.token_antifalsificacao
            if isinstance(json_payload, dict) and not json_payload.get("__RequestVerificationToken"):
                json_payload["__RequestVerificationToken"] = self.token_antifalsificacao
            headers.setdefault("RequestVerificationToken", self.token_antifalsificacao)

        return {
            "metodo": metodo.lower(),
            "url": url,
            "params": params,
            "data": data,
            "json": json_payload,
            "headers": headers,
            "cookies": cookies,
        }

    @staticmethod
    @request(cache=False, raise_exception=True, create_error_logs=False, output=None)
    def _enviar(req: Request, args: dict):
        metodo = args["metodo"]
        url = args["url"]
        return getattr(req, metodo)(
            url,
            params=args["params"],
            data=args["data"],
            json=args["json"],
            headers=args["headers"],
            cookies=args["cookies"],
        )


__all__ = [
    "BaseRequest",
    "SessaoSolicitacoes",
    "ParametrosManualSolicitacao",
]

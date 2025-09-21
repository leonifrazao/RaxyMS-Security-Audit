# base_request.py

import json
from pathlib import Path
from urllib.parse import urljoin
from botasaurus.soupify import soupify
from botasaurus.request import request, Request


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

    def executar(self, diretorio_template, bypass_request_token=False):
        template = self._carregar(diretorio_template)
        args = self._montar(template, bypass_request_token)
        return self._enviar(args)

    def _carregar(self, diretorio_template):
        caminho = diretorio_template
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)

    def _montar(self, template, bypass_request_token):
        metodo = str(template.get("method", "GET")).upper()

        # URL
        if "url" in template:
            url = str(template["url"])
        else:
            destino = str(template.get("path", ""))
            url = urljoin(self.url_base.rstrip("/") + "/", destino.lstrip("/"))

        # headers
        headers = dict(template.get("headers") or {})
        headers.setdefault("User-Agent", self.user_agent)

        # cookies
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

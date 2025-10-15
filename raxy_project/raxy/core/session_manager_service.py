# raxy/core/session_manager_service.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from botasaurus.browser import Driver, Wait, browser
from botasaurus.lang import Lang
from botasaurus.soupify import soupify
from botasaurus.request import Request, request

from raxy.domain.accounts import Conta
from raxy.core.network_service import NetWork
from raxy.services.logging_service import log


def _extract_request_verification_token(html: str | None) -> str | None:
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


class ProxyRotationRequiredException(Exception):
    """Sinaliza necessidade de rotacionar a proxy quando um erro HTTP 400+ ocorre durante login/fluxo."""
    def __init__(self, status_code: int, proxy_id: str | int | None):
        self.status_code = status_code
        self.proxy_id = proxy_id
        super().__init__(f"Erro HTTP {status_code} — rotacionar proxy (ID: {proxy_id})")


class SessionManagerService:
    """
    Serviço único de sessão:
    - Abre/fecha driver do Botasaurus
    - Faz login no Rewards (fluxo idêntico ao original)
    - Mantém cookies, UA e token antifalsificação
    - Executa templates declarativos via @request
    """

    def __init__(self, conta: Conta, proxy: dict | None = None) -> None:
        self.conta = conta
        self.proxy = proxy or {}
        self.driver: Driver | None = None
        self.network: NetWork | None = None
        self.cookies: dict[str, str] = {}
        self.user_agent: str = ""
        self.token_antifalsificacao: str | None = None
        self._logger = log.com_contexto(conta=conta.email, perfil=(conta.id_perfil or conta.email))

    @browser(
        reuse_driver=False,
        remove_default_browser_check_argument=True,
        wait_for_complete_page_load=False,
        raise_exception=True,
        close_on_crash=True,
        block_images=True,
        output=None,
        tiny_profile=True,
        lang=Lang.English
    )
    def _abrir_driver(driver: Driver, data: Mapping[str, Any] | None = None) -> dict[str, Any]:
        registro = log.com_contexto(fluxo="session_manager_login", perfil=driver.config.profile)
        proxy_id = (data or {}).get("proxy_id")
        registro.debug("Abrindo Rewards e iniciando login (se necessário)", proxy_id=proxy_id)

        driver.enable_human_mode()
        driver.google_get("https://rewards.bing.com/")
        driver.short_random_sleep()

        if driver.run_js("return document.title").lower() == "microsoft rewards":
            registro.sucesso("Conta já autenticada")
            html = soupify(driver)
            registro.info("Coletando cookies do domínio de pesquisa...")
            driver.google_get("https://www.bing.com")
            driver.short_random_sleep()
            token = _extract_request_verification_token(html)
            return {
                "cookies": driver.get_cookies_dict(),
                "ua": driver.profile.get("UA"),
                "token": token,
                "driver": driver,
            }

        if not driver.is_element_present("input[type='email']", wait=Wait.VERY_LONG):
            registro.erro("Campo de email não encontrado na página, rotação de proxy necessária")
            raise ProxyRotationRequiredException(400, proxy_id)

        email_normalizado = str(driver.profile.get("email", "")).strip()
        senha_normalizada = str(driver.profile.get("senha", "")).strip()
        if not email_normalizado or "@" not in email_normalizado:
            registro.erro("Email ausente/ inválido para login do Rewards")
            raise ValueError("Email ausente ou inválido para login do Rewards")
        if not senha_normalizada:
            registro.erro("Senha ausente para login do Rewards")
            raise ValueError("Senha ausente para login do Rewards")

        registro.info("Digitando email")
        driver.type("input[type='email']", email_normalizado, wait=Wait.VERY_LONG)
        driver.click("button[type='submit']")
        driver.short_random_sleep()

        if driver.run_js("return document.title").lower() == "verify your email" and driver.is_element_present("#view > div > span:nth-child(6) > div > span", wait=Wait.VERY_LONG):
            driver.click("#view > div > span:nth-child(6) > div > span")

        if not driver.is_element_present("input[type='password']", wait=Wait.VERY_LONG):
            registro.erro("Campo de senha não encontrado após informar email")
            raise RuntimeError("Campo de senha não encontrado após informar email")

        registro.info("Digitando senha")
        driver.type("input[type='password']", senha_normalizada, wait=Wait.VERY_LONG)
        driver.click("button[type='submit']")
        driver.short_random_sleep()

        try:
            driver.click("button[data-testid='primaryButton']", wait=Wait.SHORT)
        except Exception:
            pass
        else:
            registro.debug("Confirmação de sessão (Stay signed in) aceita")

        network = NetWork(driver)
        network.limpar_respostas()

        if driver.is_element_present("h1[ng-bind-html='$ctrl.nameHeader']", wait=Wait.VERY_LONG):
            registro.sucesso("Login finalizado")

            status_final = network.get_status()
            if status_final == 200:
                registro.sucesso(f"Login bem-sucedido - Status: {status_final}")
            elif status_final is not None:
                registro.aviso(f"Login concluído mas com status inesperado: {status_final}")
            else:
                registro.debug("Nenhum status HTTP registrado após login")

            html = soupify(driver)
            registro.info("Coletando cookies do domínio de pesquisa...")
            driver.google_get("https://www.bing.com")
            driver.short_random_sleep()

            token = _extract_request_verification_token(html)
            return {
                "cookies": driver.get_cookies_dict(),
                "ua": driver.profile.get("UA"),
                "token": token,
                "driver": driver,
            }

        status = network.get_status()
        if status and status >= 400:
            registro.erro(f"Erro HTTP detectado: {status}")
            raise ProxyRotationRequiredException(status, proxy_id)

        if status is not None:
            registro.erro("Login não confirmado mesmo após tentativa", status=status)
        else:
            registro.erro("Login não confirmado: nenhuma resposta de rede capturada")

        raise RuntimeError(f"Não foi possível confirmar o login para {email_normalizado}.")

    def start(self) -> None:
        perfil = self.conta.id_perfil or self.conta.email
        dados = {"proxy_id": self.proxy.get("id")}
        self._logger.info("Iniciando sessão/driver", perfil=perfil, proxy_id=dados["proxy_id"])

        # CHAMADA CORRETA
        ctx = SessionManagerService._abrir_driver(profile=perfil, proxy=self.proxy.get("url"), data=dados)

        self.driver = ctx["driver"]
        self.cookies = ctx["cookies"]
        self.user_agent = ctx["ua"]
        self.token_antifalsificacao = ctx["token"]
        self.network = NetWork(self.driver)
        self.network.limpar_respostas()
        self._logger.sucesso("Sessão iniciada com sucesso.")

    @staticmethod
    @request(cache=False, raise_exception=True, create_error_logs=False, output=None)
    def _enviar(req: Request, args: dict, proxy: str | None = None):
        metodo = args.pop("metodo")
        return getattr(req, metodo)(**args)

    def execute_template(
        self,
        template_path_or_dict: str | Path | Mapping[str, Any],
        *,
        placeholders: Mapping[str, Any] | None = None,
        use_ua: bool = True,
        use_cookies: bool = True,
        bypass_request_token: bool = True,
    ) -> Any:
        if not self.driver:
            raise RuntimeError("Sessão não iniciada")

        if isinstance(template_path_or_dict, (str, Path)):
            with open(template_path_or_dict, encoding="utf-8") as f:
                template = json.load(f)
        else:
            template = dict(template_path_or_dict)

        ph = dict(placeholders or {})

        def _replace(obj: Any) -> Any:
            if isinstance(obj, str):
                for k, v in ph.items():
                    obj = obj.replace("{definir}", str(v)).replace("{"+str(k)+"}", str(v))
                return obj
            if isinstance(obj, dict):
                return {k: _replace(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_replace(v) for v in obj]
            return obj

        template = _replace(template)

        metodo = str(template.get("method", "GET")).lower()
        url = template.get("url") or template.get("path")
        headers = dict(template.get("headers") or {})
        cookies = dict(template.get("cookies") or {})

        if use_ua and self.user_agent:
            headers.setdefault("User-Agent", self.user_agent)
        if use_cookies:
            cookies = {**self.cookies, **cookies}

        data = template.get("data")
        json_payload = template.get("json")

        if bypass_request_token and self.token_antifalsificacao and metodo in {"post", "put", "patch", "delete"}:
            if isinstance(data, dict) and not data.get("__RequestVerificationToken"):
                data["__RequestVerificationToken"] = self.token_antifalsificacao
            if isinstance(json_payload, dict) and not json_payload.get("__RequestVerificationToken"):
                json_payload["__RequestVerificationToken"] = self.token_antifalsificacao
            headers.setdefault("RequestVerificationToken", self.token_antifalsificacao)

        args = {
            "metodo": metodo,
            "url": url,
            "headers": headers,
            "cookies": cookies,
            "data": data,
            "json": json_payload,
        }

        resposta = self._enviar(args, proxy=self.proxy.get("url"))
        status = getattr(resposta, "status_code", None)
        if status and status >= 400:
            raise ProxyRotationRequiredException(status, self.proxy.get("id"))
        return resposta

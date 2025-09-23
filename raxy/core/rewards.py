# rewards.py

from __future__ import annotations
import json
import traceback
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from botasaurus.browser import browser, Driver, Wait
from .logging import log
from .session import BaseRequest
from .network import NetWork

REQUESTS_DIR = Path(__file__).resolve().parents[1] / "requests"


class Rewards:
    """Cliente unificado para o Microsoft Rewards."""

    _TEMPLATE_OBTER_PONTOS = "rewards_obter_pontos.json"
    _TEMPLATE_EXECUTAR_TAREFA = "pegar_recompensa_rewards.json"

    def __init__(self, palavras_erro: list[str] | None = None):
        self.base = None
        self.palavras_erro = palavras_erro or ["captcha", "temporarily unavailable", "error"]

    # -------------------------
    # Fluxos com navegador
    # -------------------------
    @staticmethod
    @browser(reuse_driver=False)
    def open_rewards_page(driver: Driver, data: dict | None = None) -> None:
        """Abre a página de Rewards.

        data: {"url": "<opcional>"}
        """
        data = data or {}
        url = data.get("url") or "https://rewards.bing.com/"

        driver.enable_human_mode()
        driver.google_get(url)
        html = getattr(driver, "page_source", "") or ""
        if "Sign in" in html or "Entrar" in html:
            print("You are not logged in. Please log in to access rewards.")
        driver.prompt()  # pausa interativa do Botasaurus

    @staticmethod
    @browser(
        reuse_driver=False,
        remove_default_browser_check_argument=True,
        wait_for_complete_page_load=True,
        block_images=True,
        output=None,
        tiny_profile=True,
    )
    def login(driver: Driver, data: dict | None = None) -> BaseRequest:
        """Realiza login e retorna uma BaseRequest pronta para uso.

        data: {"email": "...", "password": "..."}  (aceita também "senha")
        """
        data = data or {}
        email_normalizado = (data.get("email") or "").strip()
        senha_normalizada = (data.get("password") or data.get("senha") or "").strip()

        network = NetWork(driver)
        network.limpar_respostas()

        if not email_normalizado or "@" not in email_normalizado:
            raise Exception("Email ausente: defina MS_EMAIL/MS_PASSWORD ou passe em data={'email':..., 'password':...}.")

        if not senha_normalizada:
            raise Exception("Senha ausente: defina MS_EMAIL/MS_PASSWORD ou passe em data={'email':..., 'password':...}.")

        registro = log.com_contexto(fluxo="login", perfil=driver.config.profile)
        registro.debug("Coletando credenciais")

        driver.enable_human_mode()
        driver.google_get("https://rewards.bing.com/")
        driver.short_random_sleep()

        if driver.is_element_present("h1[ng-bind-html='$ctrl.nameHeader']", wait=Wait.VERY_LONG):
            registro.sucesso("Conta já autenticada")            
            base_request = BaseRequest(driver.config.profile, driver)
            registro.debug("Sessão pronta para requests",
                           perfil=driver.config.profile,
                           total_cookies=len(driver.get_cookies_dict()))
            return base_request

        if not driver.is_element_present("input[type='email']", wait=Wait.VERY_LONG):
            registro.erro("Campo de email não encontrado na página")
            raise RuntimeError("Campo de email não encontrado na página de login")

        registro.info("Digitando email")
        driver.type("input[type='email']", email_normalizado, wait=Wait.VERY_LONG)
        driver.click("button[type='submit']")
        driver.short_random_sleep()

        if not driver.is_element_present("input[type='password']", wait=Wait.VERY_LONG):
            registro.erro("Campo de senha não encontrado após informar email")
            raise RuntimeError("Campo de senha não encontrado após informar email")

        registro.info("Digitando senha")
        driver.type("input[type='password']", senha_normalizada, wait=Wait.VERY_LONG)
        driver.click("button[type='submit']")
        driver.short_random_sleep()

        try:
            driver.click("button[aria-label='Yes']", wait=Wait.SHORT)
        except Exception:
            pass
        else:
            registro.debug("Confirmação de sessão aceita")

        if driver.is_element_present("h1[ng-bind-html='$ctrl.nameHeader']", wait=Wait.VERY_LONG):
            registro.sucesso("Login finalizado")

            status_final = network.get_status()
            if status_final == 200:
                registro.sucesso(f"Login bem-sucedido - Status: {status_final}")
            elif status_final is not None:
                registro.aviso(f"Login concluído mas com status inesperado: {status_final}")
            else:
                registro.debug("Nenhum status HTTP registrado após login")

            base_request = BaseRequest(driver.config.profile, driver)
            registro.debug("Sessão pronta para requests",
                           perfil=driver.config.profile,
                           total_cookies=len(driver.get_cookies_dict()))
            return base_request

        status = network.get_status()
        if status and status >= 400:
            registro.erro(f"Erro HTTP detectado: {status}")
            raise RuntimeError(f"Erro HTTP durante login: {status}")

        if status is not None:
            registro.erro("Login não confirmado mesmo após tentativa", status=status)
        else:
            registro.erro("Login não confirmado: nenhuma resposta de rede capturada")

        raise RuntimeError(f"Não foi possível confirmar o login para {email_normalizado}.")

    # -------------------------
    # Chamadas de API de alto nível (usam self.base)
    # -------------------------
    def obter_pontos(self, base: BaseRequest, bypass_request_token: bool = False) -> dict:
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
        for palavra in self.palavras_erro:
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

    def obter_recompensas(self, base: BaseRequest, bypass_request_token: bool = False) -> dict:
        # Usar o template correto (antes estava o de pontos)
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
        for item in dashboard.get("morePromotionsWithoutPromotionalItems") or []:
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

    def pegar_recompensas(self, base: BaseRequest, bypass_request_token: bool = False) -> list[dict]:
        """Executa todas as promoções de Daily Sets encontradas."""

        recompensas = self.obter_recompensas(base, bypass_request_token=bypass_request_token)
        daily_sets = recompensas.get("daily_sets", []) if isinstance(recompensas, dict) else []
        if not daily_sets:
            return []

        template_path = REQUESTS_DIR / self._TEMPLATE_EXECUTAR_TAREFA
        with open(template_path, encoding="utf-8") as arquivo:
            template_base = json.load(arquivo)

        resultados = []
        for conjunto in daily_sets:
            data_referencia = conjunto.get("date")
            promocoes_resultado = []
            for promocao in conjunto.get("promotions", []):
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
                # print(base.token_antifalsificacao)

                argumentos = base._montar(template, bypass_request_token=bypass_request_token)
                # print(argumentos)
                try:
                    resposta = base._enviar(argumentos)
                    # print(resposta.json())
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

            if promocoes_resultado:
                resultados.append({"date": data_referencia, "promotions": promocoes_resultado})

        return resultados

    # -------------------------
    # Helpers
    # -------------------------
    def _montar_promocao(self, item, data_ref=None):
        attrs = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}

        pontos = self._para_int(item.get("pointProgressMax")) \
                 or self._para_int(attrs.get("max")) \
                 or self._para_int(attrs.get("link_text"))

        tipo = None
        for chave in ("type", "promotionType", "promotionSubtype"):
            val = item.get(chave) or attrs.get(chave)
            if isinstance(val, str):
                val = val.strip()
                if val:
                    tipo = val
                    break

        return {
            "id": item.get("name") or item.get("offerId"),
            "hash": item.get("hash"),
            "title": item.get("title") or attrs.get("title"),
            "description": item.get("description") or attrs.get("description"),
            "points": pontos,
            "complete": bool(item.get("complete") or str(attrs.get("complete")).lower() == "true"),
            "url": item.get("destinationUrl") or attrs.get("destination"),
            "date": data_ref,
            "type": tipo,
        }

    @staticmethod
    def _para_int(valor):
        if isinstance(valor, (int, float)):
            return int(valor)
        if isinstance(valor, str):
            numeros = [ch for ch in valor if ch.isdigit()]
            if numeros:
                return int("".join(numeros))
        return None

    @staticmethod
    def _registrar_erro(parametros, chamada, resposta_registro=None, erro_registro=None, extras_registro=None):
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

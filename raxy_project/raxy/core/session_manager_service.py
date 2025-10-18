from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

# Importações para o Gerenciamento de Perfil/UA
from random_user_agent.params import OperatingSystem, SoftwareName
from random_user_agent.user_agent import UserAgent
from botasaurus.profiles import Profiles

from botasaurus.browser import Driver, Wait, browser
from botasaurus.lang import Lang
from botasaurus.request import Request, request
from botasaurus.soupify import soupify

from raxy.domain.accounts import Conta
from raxy.core.network_service import NetWork
from raxy.services.logging_service import log
from raxy.core.exceptions import (
    SessionException,
    ProxyRotationRequiredException,
    ProfileException,
    InvalidCredentialsException,
    ElementNotFoundException,
    LoginException,
    wrap_exception,
)
def _extract_request_verification_token(html: str | None) -> str | None:
    """Extrai o token de verificação do HTML, retornando None em caso de falha."""
    if not html:
        return None
    try:
        soup = soupify(html)
        campo = soup.find("input", {"name": "__RequestVerificationToken"})
        if campo and campo.get("value"):
            return campo["value"].strip() or None
    except Exception as e:
        log.debug("Falha ao extrair token de verificação", erro=str(e))
        return None
    return None




class SessionManagerService:
    """
    Serviço único de sessão:
    - Abre/fecha driver do Botasaurus
    - Faz login no Rewards (fluxo idêntico ao original)
    - Mantém cookies, UA e token antifalsificação
    - Executa templates declarativos via @request
    """

    _SOFTWARES_PADRAO = [SoftwareName.EDGE.value]
    _SISTEMAS_PADRAO = [
        OperatingSystem.WINDOWS.value,
        OperatingSystem.LINUX.value,
        OperatingSystem.MACOS.value,
    ]

    def __init__(
        self, 
        conta: Conta, 
        proxy: dict | None = None, 
        proxy_service: IProxyService | None = None,
        mail_service: IMailTmService | None = None,
    ) -> None:
        self.conta = conta
        self.proxy = proxy or {}
        self.driver: Driver | None = None
        self.network: NetWork | None = None
        self.cookies: dict[str, str] = {}
        self.user_agent: str = ""
        self.token_antifalsificacao: str | None = None
        self._logger = log.com_contexto(conta=conta.email, perfil=(conta.id_perfil or conta.email))
        self._proxy_service = proxy_service
        self._mail_service = mail_service
        
        self._ua_provedor = UserAgent(
            limit=100,
            software_names=self._SOFTWARES_PADRAO,
            operating_systems=self._SISTEMAS_PADRAO,
        )

    # --- Métodos de Perfil Integrados e Simplificados ---
    
    def _garantir_perfil(self, perfil: str) -> list[str]:
        """
        Garante que o perfil exista e retorna os argumentos de linha de comando
        com o User-Agent do perfil.
        """
        if not perfil:
            raise ProfileException("Perfil deve ser informado", details={"conta": self.conta.email})
        
        try:
            email = self.conta.email
            senha = self.conta.senha
            perfil_data = Profiles.get_profile(perfil)
        except Exception as e:
            raise wrap_exception(e, ProfileException, "Erro ao acessar perfil", perfil=perfil, conta=self.conta.email)
        
        if not perfil_data:
            if not self._mail_service:
                self._logger.erro("IMailTmService não foi fornecido. Não é possível criar novo perfil.")
                raise ProfileException(
                    "IMailTmService é obrigatório para garantir um novo perfil.",
                    details={"perfil": perfil, "conta": self.conta.email}
                )

            self._logger.info(f"Perfil '{perfil}' não encontrado. Criando novo perfil e e-mail temporário.")
            
            try:
                # 1. Cria conta de email temporário
                #random_email_account = self._mail_service.create_random_account(password=senha)
                
                # 2. Gera um novo UA
                novo_ua = self._ua_provedor.get_random_user_agent()
                
                # 3. Persiste os dados no perfil
                Profiles.set_profile(perfil, {
                    "UA": novo_ua, 
                    "email": email, 
                    "senha": senha, 
                    #"tmpmail_mail": random_email_account.get("address")
                })
                self._logger.sucesso(f"Novo perfil '{perfil}' criado com UA e credenciais salvas.")
                agente = novo_ua
            except Exception as e:
                raise wrap_exception(
                    e, ProfileException,
                    "Erro ao criar novo perfil",
                    perfil=perfil, conta=self.conta.email
                )
        else:
            # Perfil existe, recupera o UA
            agente = perfil_data.get("UA")
            if not agente:
                # Caso extremo: perfil existe mas UA foi perdido, regenera e salva.
                agente = self._ua_provedor.get_random_user_agent()
                Profiles.set_profile(perfil, {**perfil_data, "UA": agente})
                self._logger.aviso(f"User-Agent regenerado e salvo para o perfil '{perfil}'.")

        # Retorna o argumento User-Agent no formato esperado pelo Botasaurus
        return [f"--user-agent={agente}"]


    # --- Métodos de Sessão (Browser e Request) ---

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
        """Método estático que abre o driver, realiza o login e retorna os dados da sessão."""
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
            if driver.is_element_present('span[id="id_s"]', wait=Wait.VERY_LONG):
                registro.info("Conta logada com sucesso no bing")
            else:
                registro.aviso("Conta não logada no bing")
            
            token = _extract_request_verification_token(html)
            return {
                "cookies": driver.get_cookies_dict(),
                "ua": driver.profile.get("UA"),
                "token": token,
                "driver": driver,
            }

        # Lógica de login e tratamento de exceções
        if not driver.is_element_present("input[type='email']", wait=Wait.VERY_LONG):
            registro.erro("Campo de email não encontrado na página, rotação de proxy necessária")
            raise ProxyRotationRequiredException(400, proxy_id, url=driver.current_url)

        email_normalizado = str(driver.profile.get("email", "")).strip()
        senha_normalizada = str(driver.profile.get("senha", "")).strip()
        if not email_normalizado or "@" not in email_normalizado:
            registro.erro("Email ausente/inválido para login do Rewards")
            raise InvalidCredentialsException(
                "Email ausente ou inválido para login do Rewards",
                details={"email": email_normalizado}
            )
        if not senha_normalizada:
            registro.erro("Senha ausente para login do Rewards")
            raise InvalidCredentialsException(
                "Senha ausente para login do Rewards",
                details={"email": email_normalizado}
            )

        registro.info("Digitando email")
        try:
            driver.type("input[type='email'], #i0116", email_normalizado, wait=Wait.VERY_LONG)
            driver.click("button[type='submit'], #idSIButton9")
            driver.short_random_sleep()
        except Exception as e:
            raise wrap_exception(
                e, ElementNotFoundException,
                "Erro ao interagir com campo de email",
                email=email_normalizado
            )

        if driver.run_js("return document.title").lower() == "verify your email" and driver.is_element_present("#view > div > span:nth-child(6) > div > span", wait=Wait.VERY_LONG):
            driver.click("#view > div > span:nth-child(6) > div > span")

        if not driver.is_element_present("input[type='password'], #i0118", wait=Wait.VERY_LONG):
            registro.erro("Campo de senha não encontrado após informar email")
            raise ElementNotFoundException(
                "Campo de senha não encontrado após informar email",
                details={"email": email_normalizado, "url": driver.current_url}
            )

        registro.info("Digitando senha")
        try:
            driver.type("input[type='password'], #i0118", senha_normalizada, wait=Wait.VERY_LONG)
            driver.click("button[type='submit'], #idSIButton9")
            driver.short_random_sleep()
        except Exception as e:
            raise wrap_exception(
                e, ElementNotFoundException,
                "Erro ao interagir com campo de senha",
                email=email_normalizado
            )
        
        while driver.run_js("return document.title").lower() == "let's protect your account":
            driver.short_random_sleep()
            driver.click("a[id='iShowSkip']", wait=Wait.LONG)
            driver.short_random_sleep()

        try:
            driver.click("button[data-testid='primaryButton']", wait=Wait.SHORT)
        except Exception:
            pass
        else:
            registro.debug("Confirmação de sessão (Stay signed in) aceita")

        network = NetWork(driver)
        network.limpar_respostas()

        if "rewards.bing.com" in driver.current_url or driver.is_element_present("span[role='presentation']", wait=Wait.VERY_LONG):
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
            if driver.is_element_present('span[id="id_s"]', wait=Wait.VERY_LONG):
                registro.info("Conta logada com sucesso no bing")
            else:
                registro.aviso("Conta não logada no bing")
            
            driver.google_get("https://www.bing.com/rewards/panelflyout?channel=bingflyout&partnerId=BingRewards&isDarkMode=1&requestedLayout=onboarding&form=rwfobc")
            driver.short_random_sleep()
            if driver.is_element_present('a[class="joinNowText"]', wait=Wait.VERY_LONG):
                driver.click('a[class="joinNowText"]')
                driver.short_random_sleep()
            while not driver.is_element_present('span[id="id_s"]', wait=Wait.VERY_LONG):
                driver.short_random_sleep()
            driver.google_get("https://www.bing.com/rewards/panelflyout?channel=bingflyout&partnerId=BingRewards&isDarkMode=1&requestedLayout=onboarding&form=rwfobc")
            driver.short_random_sleep()
            if driver.is_element_present('div[id="Card_0"]', wait=Wait.LONG):
                registro.info("Cartões de metas detectados no flyout.")
                
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
            raise ProxyRotationRequiredException(status, proxy_id, url=driver.current_url)

        if status is not None:
            registro.erro("Login não confirmado mesmo após tentativa", status=status)
        else:
            registro.erro("Login não confirmado: nenhuma resposta de rede capturada")

        raise LoginException(
            f"Não foi possível confirmar o login para {email_normalizado}.",
            details={"email": email_normalizado, "status": status, "url": driver.current_url}
        )

    def start(self) -> None:
        """Inicia a sessão com tratamento robusto de erros."""
        perfil_nome = self.conta.id_perfil or self.conta.email
        dados = {"proxy_id": self.proxy.get("id")}
        
        # 1. GARANTIR PERFIL e OBTER ARGS UA em uma única chamada
        self._logger.info("Garantindo perfil e obtendo argumentos do User-Agent...")
        try:
            # user_agent_args recebe o valor de retorno de _garantir_perfil
            user_agent_args = self._garantir_perfil(perfil_nome)
            self._logger.sucesso(f"Perfil '{perfil_nome}' pronto. Argumentos UA obtidos: {user_agent_args}")
        except ProfileException:
            raise
        except Exception as e:
            raise wrap_exception(
                e, ProfileException,
                "Erro inesperado ao garantir perfil",
                perfil=perfil_nome, conta=self.conta.email
            )
        
        self._logger.info("Iniciando sessão/driver", perfil=perfil_nome, proxy_id=dados["proxy_id"])

        tentativas = 5
        
        while tentativas > 0:
            try:
                # 2. INICIAR SESSÃO/DRIVER com os argumentos
                resultado = SessionManagerService._abrir_driver(
                    profile=perfil_nome, 
                    proxy=self.proxy.get("url"), 
                    data=dados,
                    browser_arguments=user_agent_args # USANDO OS ARGUMENTOS
                )
                
                # 3. Atribuição direta a self
                self.driver = resultado["driver"]
                self.cookies = resultado["cookies"]
                self.user_agent = resultado["ua"] 
                self.token_antifalsificacao = resultado["token"]
                break
                
            except ProxyRotationRequiredException as e:
                self._logger.aviso(f"Exceção de rotação: {e}. Tentando próxima proxy.")
                if self._proxy_service:
                    try:
                        self._proxy_service.rotate_proxy(self.proxy.get("id"))
                    except Exception as rotate_err:
                        self._logger.erro(f"Erro ao rotacionar proxy: {rotate_err}")
                        if tentativas == 1:
                            raise wrap_exception(
                                rotate_err, ProxyRotationRequiredException,
                                "Falha ao rotacionar proxy",
                                proxy_id=self.proxy.get("id"), attempts_left=tentativas
                            )
                else:
                    self._logger.erro("ProxyRotationRequiredException, mas _proxy_service ausente para rotação.")
                    raise e
            except (LoginException, InvalidCredentialsException, ElementNotFoundException):
                # Exceções de login não devem ser retentadas
                raise
            except Exception as e:
                self._logger.erro(f"Erro inesperado ao abrir driver: {e}", erro=e, tentativas_restantes=tentativas-1)
                if tentativas == 1:
                    raise wrap_exception(
                        e, SessionException,
                        "Falha ao iniciar sessão após múltiplas tentativas",
                        conta=self.conta.email, proxy_id=self.proxy.get("id")
                    )
            finally:
                tentativas -= 1
        
        if not self.driver:
            raise SessionException(
                "Falha ao iniciar a sessão após 5 tentativas.",
                details={"conta": self.conta.email, "proxy_id": self.proxy.get("id")}
            )

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
        """Executa um template de requisição com tratamento robusto de erros."""
        if not self.driver:
            raise SessionException(
                "Sessão não iniciada",
                details={"conta": self.conta.email}
            )

        try:
            if isinstance(template_path_or_dict, (str, Path)):
                with open(template_path_or_dict, encoding="utf-8") as f:
                    template = json.load(f)
            else:
                template = dict(template_path_or_dict)
        except FileNotFoundError as e:
            raise wrap_exception(
                e, SessionException,
                "Template não encontrado",
                template=str(template_path_or_dict)
            )
        except json.JSONDecodeError as e:
            raise wrap_exception(
                e, SessionException,
                "Template JSON inválido",
                template=str(template_path_or_dict)
            )
        except Exception as e:
            raise wrap_exception(
                e, SessionException,
                "Erro ao carregar template",
                template=str(template_path_or_dict)
            )

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

        try:
            resposta = self._enviar(args, proxy=self.proxy.get("url"))
        except Exception as e:
            raise wrap_exception(
                e, SessionException,
                "Erro ao enviar requisição",
                url=args.get("url"), metodo=args.get("metodo")
            )
        
        status = getattr(resposta, "status_code", None)
        if status and status >= 400:
            raise ProxyRotationRequiredException(status, self.proxy.get("id"), url=args.get("url"))
        return resposta
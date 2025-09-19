"""Fluxo de autenticacao com validacoes robustas e orientacao a objetos."""

import os
import re
from typing import Any, Mapping

from botasaurus.browser import browser, Driver, Wait

from .config import BROWSER_KWARGS, REWARDS_BASE_URL
from .logging import log
from .solicitacoes import GerenciadorSolicitacoesRewards
from .network import NetWork


class CredenciaisInvalidas(ValueError):
    """Erro levantado quando email ou senha nao atendem aos requisitos."""


class AutenticadorRewards:
    """Responsavel por realizar o login no Microsoft Rewards."""

    _PADRAO_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

    @classmethod
    def validar_credenciais(cls, email: str, senha: str) -> tuple[str, str]:
        """Normaliza entradas de email/senha e aplica regras basicas."""

        email_normalizado = email.strip()
        senha_normalizada = senha.strip()

        if not email_normalizado:
            raise CredenciaisInvalidas(
                "Email ausente: defina MS_EMAIL/MS_PASSWORD ou passe em data={}."
            )
        if not cls._PADRAO_EMAIL.match(email_normalizado):
            raise CredenciaisInvalidas(
                "Email invalido: informe um endereco no formato usuario@dominio."
            )
        if not senha_normalizada:
            raise CredenciaisInvalidas(
                "Senha ausente: defina MS_EMAIL/MS_PASSWORD ou passe em data={}."
            )

        return email_normalizado, senha_normalizada

    @classmethod
    def _registrar_solicitacoes(
        cls,
        driver: Driver,
        perfil_sessao: str,
        registro,
    ) -> GerenciadorSolicitacoesRewards:
        """Gera um gerenciador de solicitações autenticado a partir do driver.

        Args:
            driver: Instância do botasaurus utilizada no fluxo de login.
            perfil_sessao: Identificador do perfil usado na automação.
            registro: Logger contextual para reportar métricas.

        Returns:
            Gerenciador de solicitações pronto para criar clientes HTTP.
        """

        gestor = GerenciadorSolicitacoesRewards(perfil_sessao, driver)
        sessao = gestor.capturar()
        registro.debug(
            "Sessao pronta para requests",
            perfil=perfil_sessao,
            total_cookies=len(sessao.cookies),
        )
        return gestor

    @staticmethod
    @browser(**BROWSER_KWARGS)
    def executar(driver: Driver, dados: Mapping[str, Any] | None = None, **outros: Any) -> None:
        """Executa o fluxo de login do Microsoft Rewards com validações extras.

        Args:
            driver: Instância controlada pelo decorator ``@browser``.
            dados: Dicionário opcional contendo ``email`` e ``senha``.
            **outros: Argumentos adicionais aceitos pelo decorator (``profile``,
                ``add_arguments`` etc.).

        Returns:
            ``GerenciadorSolicitacoesRewards`` ou ``None`` (mantido por compatibilidade).

        Raises:
            CredenciaisInvalidas: Quando email ou senha são inválidos.
            RuntimeError: Quando elementos essenciais não são encontrados na página.
        """

        if not dados and "data" in outros:
            dados = outros["data"]

        dados = dados or {}
        perfil = outros.get("profile")
        contexto = {"fluxo": "login"}
        if perfil:
            contexto["perfil"] = perfil
        registro = log.com_contexto(**contexto)
        registro.debug("Coletando credenciais")

        network = NetWork(driver)
        network.limpar_respostas()

        entrada_email = dados.get("email") or os.getenv("MS_EMAIL") or ""
        entrada_senha = (
            dados.get("senha")
            or dados.get("password")
            or os.getenv("MS_PASSWORD")
            or ""
        )

        try:
            email_validado, senha_validada = AutenticadorRewards.validar_credenciais(entrada_email, entrada_senha)
        except CredenciaisInvalidas as exc:
            registro.erro("Credenciais invalidas", detalhe=str(exc))
            raise

        driver.enable_human_mode()
        driver.google_get(REWARDS_BASE_URL)
        driver.short_random_sleep()

        if driver.is_element_present("h1[ng-bind-html='$ctrl.nameHeader']", wait=Wait.VERY_LONG):
            registro.sucesso("Conta ja autenticada")
            return AutenticadorRewards._registrar_solicitacoes(
                driver,
                perfil or entrada_email,
                registro,
            )

        if not driver.is_element_present("input[type='email']", wait=Wait.VERY_LONG):
            registro.erro("Campo de email nao encontrado na pagina")
            raise RuntimeError("Campo de email nao encontrado na pagina de login")

        registro.info("Digitando email")
        driver.type("input[type='email']", email_validado, wait=Wait.VERY_LONG)
        driver.click("button[type='submit']")
        driver.short_random_sleep()

        if not driver.is_element_present("input[type='password']", wait=Wait.VERY_LONG):
            registro.erro("Campo de senha nao encontrado apos informar email")
            raise RuntimeError("Campo de senha nao encontrado apos informar email")

        registro.info("Digitando senha")
        driver.type("input[type='password']", senha_validada, wait=Wait.VERY_LONG)
        driver.click("button[type='submit']")
        driver.short_random_sleep()
        driver.prompt()

        try:
            driver.click("button[aria-label='Yes']", wait=Wait.SHORT)
        except Exception:
            pass
        else:
            registro.debug("Confirmacao de sessao aceita")

        if driver.is_element_present("h1[ng-bind-html='$ctrl.nameHeader']", wait=Wait.VERY_LONG):
            registro.sucesso("Login finalizado")

            # Verifica o status final
            status_final = network.get_status()
            if status_final == 200:
                registro.sucesso(f"Login bem-sucedido - Status: {status_final}")
            elif status_final is not None:
                registro.aviso(f"Login concluido mas com status inesperado: {status_final}")
            else:
                registro.debug("Nenhum status HTTP registrado apos login")

            return AutenticadorRewards._registrar_solicitacoes(
                driver,
                perfil or entrada_email,
                registro,
            )
        else:
            # Verifica se houve erro HTTP
            status = network.get_status()
            if status and status >= 400:
                registro.erro(f"Erro HTTP detectado: {status}")
                raise RuntimeError(f"Erro HTTP durante login: {status}")

            if status is not None:
                registro.erro(
                    "Login nao confirmado mesmo apos tentativa",
                    status=status,
                )
            else:
                registro.erro("Login nao confirmado: nenhuma resposta de rede capturada")

            raise RuntimeError(
                f"Nao foi possivel confirmar o login para {email_validado}."
            )


__all__ = ["CredenciaisInvalidas", "AutenticadorRewards"]

"""Fluxo de autenticacao com validacoes robustas e orientacao a objetos."""

import os
import re
from typing import Any, Mapping

from botasaurus.browser import browser, Driver, Wait

from .config import BROWSER_KWARGS
from .logging import log


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

    @staticmethod
    def _criar_registro(**contexto: Any):
        return log.com_contexto(fluxo="login", **{chave: valor for chave, valor in contexto.items() if valor})
    
    @staticmethod
    def _inserir_senha(driver: Driver, senha: str) -> None:
        """Insere a senha no campo apropriado, com tratamento de erros."""
        if not driver.is_element_present("input[type='password']", wait=Wait.VERY_LONG):
            raise RuntimeError("Campo de senha nao encontrado apos informar email")
        driver.type("input[type='password']", senha, wait=Wait.VERY_LONG)
        driver.click("button[type='submit']")
        driver.short_random_sleep()
        
    @staticmethod
    def _inserir_email(driver: Driver, email: str) -> None:
        """Insere o email no campo apropriado, com tratamento de erros."""
        if not driver.is_element_present("input[type='email']", wait=Wait.VERY_LONG):
            raise RuntimeError("Campo de email nao encontrado na pagina")
        driver.type("input[type='email']", email, wait=Wait.VERY_LONG)
        driver.click("button[type='submit']")
        driver.short_random_sleep()

    @staticmethod
    @browser(**BROWSER_KWARGS)
    def executar(driver: Driver, dados: Mapping[str, Any] | None = None, **outros: Any) -> None:
        """Executa o fluxo de login do Microsoft Rewards com validacoes extras."""

        dados = dados or {}
        perfil = outros.get("profile")
        registro = AutenticadorRewards._criar_registro(perfil=perfil)
        registro.debug("Coletando credenciais")

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
        driver.google_get("https://rewards.bing.com")
        driver.short_random_sleep()

        if driver.is_element_present("h1[ng-bind-html='$ctrl.nameHeader']", wait=Wait.VERY_LONG):
            registro.sucesso("Conta ja autenticada")
            return

        # Se o campo de email ja estiver presente, significa que é um novo login
        # Se não, o site pode estar pedindo a senha diretamente (sessão expirada)
        if driver.is_element_present("input[type='email']", wait=Wait.SHORT):
            registro.info("Nova Sessao, solicitando email")
            AutenticadorRewards._inserir_email(driver, email_validado)
            registro.info("Solicitando senha")
            AutenticadorRewards._inserir_senha(driver, senha_validada)
        elif driver.is_element_present("input[type='password']", wait=Wait.SHORT):
            registro.info("Sessao expirada, solicitando senha")
            AutenticadorRewards._inserir_senha(driver, senha_validada)
        else:
            registro.erro("Nao foi possivel encontrar campos de login")
            raise RuntimeError("Nao foi possivel encontrar campos de login")

        # registro.info("Digitando email")
        # driver.type("input[type='email']", email_validado, wait=Wait.VERY_LONG)
        # driver.click("button[type='submit']")
        # driver.short_random_sleep()
        # # driver.is_element_present("input[type='password']", wait=Wait.SHORT)
        # if not driver.is_element_present("input[type='password']", wait=Wait.VERY_LONG):
        #     registro.erro("Campo de senha nao encontrado apos informar email")
        #     raise RuntimeError("Campo de senha nao encontrado apos informar email")

        # registro.info("Digitando senha")
        # driver.type("input[type='password']", senha_validada, wait=Wait.VERY_LONG)
        # driver.click("button[type='submit']")
        # driver.short_random_sleep()
        driver.prompt()

        try:
            driver.click("button[aria-label='Yes']", wait=Wait.SHORT)
        except Exception:
            pass
        else:
            registro.debug("Confirmacao de sessao aceita")

        if driver.is_element_present("h1[ng-bind-html='$ctrl.nameHeader']", wait=Wait.VERY_LONG):
            registro.sucesso("Login finalizado")
        else:
            registro.aviso("Nao foi possivel confirmar o login automaticamente")


def login(*args: Any, **kwargs: Any) -> Any:
    """Alias funcional para manter compatibilidade de chamadas antigas."""

    return AutenticadorRewards.executar(*args, **kwargs)


__all__ = ["CredenciaisInvalidas", "AutenticadorRewards", "login"]

"""Fluxos relacionados à navegação e autenticação do Microsoft Rewards."""

from __future__ import annotations

import os
from typing import Any, Mapping

from botasaurus.browser import browser, Driver, Wait

from .config import BROWSER_KWARGS, REWARDS_BASE_URL
from .logging import log
from .network import NetWork
from .session import GerenciadorSolicitacoesRewards


_NAVEGADOR_OPCOES = dict(BROWSER_KWARGS)
_NAVEGADOR_OPCOES["reuse_driver"] = False


class NavegadorRecompensas:
    """Encapsula operações de navegação na página do Bing Rewards."""

    @staticmethod
    @browser(**_NAVEGADOR_OPCOES)
    def abrir_pagina(driver: Driver, data=None) -> None:
        """Abre a página principal do Rewards com as opções padrão do Botasaurus."""

        driver.enable_human_mode()
        driver.google_get(REWARDS_BASE_URL)
        html = getattr(driver, "page_source", "") or ""
        if "Sign in" in html or "Entrar" in html:
            log.aviso(
                "Parece que voce nao esta logado no Rewards",
                detalhe="Acesse https://rewards.microsoft.com/ e entre com sua conta Microsoft",
            )
        driver.prompt()


_HEADER_SELECTOR = "h1[ng-bind-html='$ctrl.nameHeader']"
_EMAIL_SELECTOR = "input[type='email']"
_PASSWORD_SELECTOR = "input[type='password']"
_SUBMIT_SELECTOR = "button[type='submit']"
_CONFIRM_SELECTOR = "button[aria-label='Yes']"


class CredenciaisInvalidas(ValueError):
    """Erro levantado quando email ou senha nao atendem aos requisitos."""


class AutenticadorRewards:
    """Responsável por realizar o login no Microsoft Rewards."""

    @classmethod
    def validar_credenciais(cls, email: str, senha: str) -> tuple[str, str]:
        """Normaliza entradas de email/senha e aplica regras básicas."""

        email_normalizado = email.strip()
        senha_normalizada = senha.strip()

        if not email_normalizado:
            raise CredenciaisInvalidas(
                "Email ausente: defina MS_EMAIL/MS_PASSWORD ou passe em data={}."
            )
        if "@" not in email_normalizado or email_normalizado.startswith("@"):
            raise CredenciaisInvalidas(
                "Email invalido: informe um endereco no formato usuario@dominio."
            )
        usuario, dominio = email_normalizado.split("@", 1)
        if not usuario or not dominio or "." not in dominio:
            raise CredenciaisInvalidas(
                "Email invalido: informe um endereco no formato usuario@dominio."
            )
        if not senha_normalizada:
            raise CredenciaisInvalidas(
                "Senha ausente: defina MS_EMAIL/MS_PASSWORD ou passe em data={}."
            )

        return email_normalizado, senha_normalizada

    @staticmethod
    @browser(**BROWSER_KWARGS)
    def executar(driver: Driver, dados: Mapping[str, Any] | None = None, **outros: Any) -> GerenciadorSolicitacoesRewards:
        """Executa o fluxo completo de login no Microsoft Rewards."""

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

        email_validado, senha_validada = AutenticadorRewards.validar_credenciais(
            entrada_email, entrada_senha
        )

        driver.enable_human_mode()
        driver.google_get(REWARDS_BASE_URL)
        driver.short_random_sleep()

        if driver.is_element_present(_HEADER_SELECTOR, wait=Wait.VERY_LONG):
            registro.sucesso("Conta ja autenticada")
            perfil_sessao = perfil or entrada_email
            gestor = GerenciadorSolicitacoesRewards(perfil_sessao, driver)
            sessao = gestor.capturar()
            registro.debug(
                "Sessao pronta para requests",
                perfil=perfil_sessao,
                total_cookies=len(sessao.cookies),
            )
            return gestor

        if not driver.is_element_present(_EMAIL_SELECTOR, wait=Wait.VERY_LONG):
            registro.erro("Campo de email nao encontrado na pagina")
            raise RuntimeError("Campo de email nao encontrado na pagina de login")

        registro.info("Digitando email")
        driver.type(_EMAIL_SELECTOR, email_validado, wait=Wait.VERY_LONG)
        driver.click(_SUBMIT_SELECTOR)
        driver.short_random_sleep()

        if not driver.is_element_present(_PASSWORD_SELECTOR, wait=Wait.VERY_LONG):
            registro.erro("Campo de senha nao encontrado apos informar email")
            raise RuntimeError("Campo de senha nao encontrado apos informar email")

        registro.info("Digitando senha")
        driver.type(_PASSWORD_SELECTOR, senha_validada, wait=Wait.VERY_LONG)
        driver.click(_SUBMIT_SELECTOR)
        driver.short_random_sleep()
        driver.prompt()

        try:
            driver.click(_CONFIRM_SELECTOR, wait=Wait.SHORT)
        except Exception:
            pass
        else:
            registro.debug("Confirmacao de sessao aceita")

        if driver.is_element_present(_HEADER_SELECTOR, wait=Wait.VERY_LONG):
            registro.sucesso("Login finalizado")

            status_final = network.get_status()
            if status_final == 200:
                registro.sucesso(f"Login bem-sucedido - Status: {status_final}")
            elif status_final is not None:
                registro.aviso(f"Login concluido mas com status inesperado: {status_final}")
            else:
                registro.debug("Nenhum status HTTP registrado apos login")

            perfil_sessao = perfil or entrada_email
            gestor = GerenciadorSolicitacoesRewards(perfil_sessao, driver)
            sessao = gestor.capturar()
            registro.debug(
                "Sessao pronta para requests",
                perfil=perfil_sessao,
                total_cookies=len(sessao.cookies),
            )
            return gestor

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


__all__ = [
    "NavegadorRecompensas",
    "CredenciaisInvalidas",
    "AutenticadorRewards",
]

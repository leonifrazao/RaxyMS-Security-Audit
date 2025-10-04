"""Componentes de autenticação e navegação no Microsoft Rewards."""

from __future__ import annotations

import re
from typing import Mapping, Optional

from raxy.domain import Conta
from raxy.interfaces.services import (
    IAutenticadorRewardsService,
    IRewardsBrowserService,
    INavegadorRewardsService,
)

from raxy.services.logging_service import log
from .rewards_browser_service import RewardsBrowserService
from raxy.core.session_service import SessaoSolicitacoes, BaseRequest
from raxy.core.network_service import NetWork


class CredenciaisInvalidas(ValueError):
    """Erro lançado quando email/senha estão ausentes ou inválidos."""


class AutenticadorRewards(IAutenticadorRewardsService):
    """Responsável por validar credenciais e iniciar a sessão."""

    _EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    def __init__(self, navegador: IRewardsBrowserService) -> None:
        self._navegador = navegador
        self._logger = log

    @classmethod
    def validar_credenciais(cls, email: str, senha: str) -> tuple[str, str]:
        """Normaliza e valida email/senha lançando ``CredenciaisInvalidas``."""

        email_normalizado = (email or "").strip()
        senha_normalizada = (senha or "").strip()

        if not email_normalizado or not cls._EMAIL_REGEX.match(email_normalizado):
            raise CredenciaisInvalidas("Email inválido")

        if not senha_normalizada:
            raise CredenciaisInvalidas("Senha inválida")

        return email_normalizado, senha_normalizada

    def executar(self, conta: Conta, proxy: dict | None = None) -> SessaoSolicitacoes:
        """
        Executa o login e cria uma SESSÃO COMPLETA, isolada para esta conta.
        Esta é a "fábrica" de objetos de sessão.
        """
        perfil = conta.id_perfil or conta.email
        logger_scoped = self._logger.com_contexto(conta=conta.email)
        logger_scoped.info("Iniciando autenticação e criação de sessão.")

        # 1. Login retorna a instância de BaseRequest (com cookies do rewards)
        sessao_base: BaseRequest = self._navegador.login(profile=perfil, proxy=proxy)

        # 3. Criamos um monitor de rede exclusivo para esta sessão.
        network_monitor = NetWork(driver=sessao_base.driver)
        
        # 4. Empacotamos tudo em um objeto de Sessão limpo e completo.
        sessao_completa = SessaoSolicitacoes(
            conta=conta,
            base_request=sessao_base,
            network_monitor=network_monitor
        )
        
        logger_scoped.sucesso("Sessão criada com sucesso.")
        return sessao_completa


class NavegadorRecompensas(INavegadorRewardsService):
    """Realiza interações simples de navegação no Rewards."""

    def __init__(self, navegador: Optional[IRewardsBrowserService] = None) -> None:
        self._navegador = navegador or RewardsBrowserService()

    def abrir_pagina(self, sessao: SessaoSolicitacoes, destino: str | None = None) -> None:
        """Abre a página de Rewards utilizando o perfil autenticado."""

        destino_dados: Mapping[str, object] | None = {"url": destino} if destino else None
        self._navegador.open_rewards_page(profile=sessao.perfil, data=destino_dados)


__all__ = [
    "AutenticadorRewards",
    "CredenciaisInvalidas",
    "NavegadorRecompensas",
]

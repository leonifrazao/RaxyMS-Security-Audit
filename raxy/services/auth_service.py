"""Componentes de autenticação e navegação no Microsoft Rewards."""

from __future__ import annotations

import re
from typing import Mapping, Optional

from domain import Conta
from interfaces.services import (
    IAutenticadorRewardsService,
    IRewardsBrowserService,
    INavegadorRewardsService,
)

from .rewards_browser_service import RewardsBrowserService
from .session_service import SessaoSolicitacoes


class CredenciaisInvalidas(ValueError):
    """Erro lançado quando email/senha estão ausentes ou inválidos."""


class AutenticadorRewards(IAutenticadorRewardsService):
    """Responsável por validar credenciais e iniciar a sessão."""

    _EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    def __init__(self, navegador: Optional[IRewardsBrowserService] = None) -> None:
        self._navegador = navegador or RewardsBrowserService()

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

    def executar(self, conta: Conta, proxy: str) -> SessaoSolicitacoes:
        """Executa o login utilizando o serviço de navegador."""

        email, senha = self.validar_credenciais(conta.email, conta.senha)
        perfil = conta.id_perfil or conta.email
        sessao_base = self._navegador.login(profile=perfil, proxy=proxy)
        sessao = SessaoSolicitacoes(conta=conta, base_request=sessao_base)
        return sessao


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

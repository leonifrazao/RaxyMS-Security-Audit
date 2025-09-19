"""Compatibilidade: reexporta interfaces agora alojadas em ``raxy.core``."""

from ..core.auth import AutenticadorRewards, CredenciaisInvalidas
from ..core.browser import NavegadorRecompensas
from ..core.rewards_api import APIRecompensas
from ..core.session import (
    GerenciadorSolicitacoesRewards,
    ClienteSolicitacoesRewards,
    SessaoSolicitacoes,
)
from ..core.profiles import GerenciadorPerfil
from ..core.accounts import Conta, carregar_contas
from ..core.config import ExecutorConfig, DEFAULT_ACTIONS, DEFAULT_API_ERROR_WORDS
from ..core.logging import log
try:
    from ..core.storage import BaseModelos
except ModuleNotFoundError:  # pragma: no cover - depende do ambiente
    BaseModelos = None  # type: ignore[assignment]

__all__ = [
    "AutenticadorRewards",
    "CredenciaisInvalidas",
    "NavegadorRecompensas",
    "APIRecompensas",
    "GerenciadorSolicitacoesRewards",
    "ClienteSolicitacoesRewards",
    "SessaoSolicitacoes",
    "GerenciadorPerfil",
    "Conta",
    "carregar_contas",
    "ExecutorConfig",
    "DEFAULT_ACTIONS",
    "DEFAULT_API_ERROR_WORDS",
    "log",
    "BaseModelos",
]

"""Interface publica dos recursos de automacao."""

from .navegacao import NavegadorRecompensas, APIRecompensas
from .autenticacao import AutenticadorRewards
from .utilitarios import GerenciadorPerfil
from .solicitacoes import (
    GerenciadorSolicitacoesRewards,
    ClienteSolicitacoesRewards,
    SessaoSolicitacoes,
)
from .contas import Conta, carregar_contas

try:  # Importacao opcional caso SQLAlchemy nao esteja disponivel
    from .base_modelos import BaseModelos
except ModuleNotFoundError:  # pragma: no cover - depende do ambiente
    BaseModelos = None  # type: ignore[assignment]
    BASE_MODELOS_DISPONIVEL = False
else:
    BASE_MODELOS_DISPONIVEL = True

__all__ = [
    "NavegadorRecompensas",
    "APIRecompensas",
    "AutenticadorRewards",
    "GerenciadorPerfil",
    "GerenciadorSolicitacoesRewards",
    "ClienteSolicitacoesRewards",
    "SessaoSolicitacoes",
    "Conta",
    "carregar_contas",
]

if BASE_MODELOS_DISPONIVEL:
    __all__.append("BaseModelos")

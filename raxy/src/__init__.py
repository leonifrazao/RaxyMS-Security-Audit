"""Interface publica dos recursos de automacao."""

from .navegacao import NavegadorRecompensas, goto_rewards_page
from .autenticacao import AutenticadorRewards, login
from .utilitarios import GerenciadorPerfil
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
    "goto_rewards_page",
    "AutenticadorRewards",
    "login",
    "GerenciadorPerfil",
    "Conta",
    "carregar_contas",
]

if BASE_MODELOS_DISPONIVEL:
    __all__.append("BaseModelos")

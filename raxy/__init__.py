"""API pública do pacote Raxy."""

from raxy.api.rewards_api import APIRecompensas
from raxy.api.rewards_data_api import RewardsDataAPI
from raxy.container import create_injector
from raxy.domain import Conta
from raxy.repositories.file_account_repository import (
    ArquivoContaRepository,
    HistoricoPontuacaoMemoriaRepository,
)
from raxy.repositories.sqlalchemy_repository import BaseModelos
from raxy.services.auth_service import AutenticadorRewards, CredenciaisInvalidas, NavegadorRecompensas
from raxy.services.executor_service import ExecutorConfig, ExecutorEmLote
from raxy.services.logging_service import FarmLogger, LoggerConfig, configurar_logging, log
from raxy.services.perfil_service import GerenciadorPerfil
from raxy.services.session_service import BaseRequest, ParametrosManualSolicitacao, SessaoSolicitacoes
from raxy.services.solicitacoes_service import GerenciadorSolicitacoesRewards
from raxy.services.rewards_browser_service import RewardsBrowserService

__all__ = [
    "APIRecompensas",
    "ArquivoContaRepository",
    "AutenticadorRewards",
    "BaseModelos",
    "BaseRequest",
    "Conta",
    "CredenciaisInvalidas",
    "ExecutorConfig",
    "ExecutorEmLote",
    "FarmLogger",
    "GerenciadorPerfil",
    "GerenciadorSolicitacoesRewards",
    "HistoricoPontuacaoMemoriaRepository",
    "LoggerConfig",
    "NavegadorRecompensas",
    "ParametrosManualSolicitacao",
    "RewardsBrowserService",
    "RewardsDataAPI",
    "SessaoSolicitacoes",
    "configurar_logging",
    "create_injector",
    "log",
]

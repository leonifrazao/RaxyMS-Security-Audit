"""Container de injeção de dependências inspirado em Ninject."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Type, TypeVar

from interfaces.repositories import IContaRepository, IDatabaseRepository
from interfaces.services import (
    IAutenticadorRewardsService,
    IExecutorEmLoteService,
    ILoggingService,
    INavegadorRewardsService,
    IPerfilService,
    IRewardsBrowserService,
    IRewardsDataService,
    IProxyService,
    IBingSuggestion
)
from repositories.file_account_repository import ArquivoContaRepository
from services.auth_service import AutenticadorRewards, NavegadorRecompensas
from services.executor_service import ExecutorConfig, ExecutorEmLote
from services.logging_service import log
from services.perfil_service import GerenciadorPerfil
from services.rewards_browser_service import RewardsBrowserService
from api.proxy import Proxy
from api.rewards_data_api import RewardsDataAPI
from api.bing_suggestion_api import BingSuggestionAPI
from api.db import SupabaseRepository


_T = TypeVar("_T")


@dataclass(slots=True)
class _Binding:
    factory: Callable[["SimpleInjector"], Any]
    singleton: bool
    instance: Any = None
    has_instance: bool = False


class SimpleInjector:
    """Container leve que oferece API similar ao Injector/Ninject."""

    def __init__(self, config: ExecutorConfig | None = None) -> None:
        self._bindings: Dict[Type[Any], _Binding] = {}
        self._config = config or ExecutorConfig()
        self._registrar_bindings_padrao()

    def _registrar_bindings_padrao(self) -> None:
        self.bind_singleton(IProxyService, lambda inj: Proxy(country="US", sources=['https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/ss_configs.txt'], use_console=True))
        self.bind_instance(ExecutorConfig, self._config)
        self.bind_singleton(ILoggingService, lambda inj: log)
        self.bind_singleton(IPerfilService, lambda inj: GerenciadorPerfil())
        self.bind_singleton(IRewardsBrowserService, lambda inj: RewardsBrowserService(proxy_service=inj.get(IProxyService)))
        self.bind_singleton(IRewardsDataService, lambda inj: RewardsDataAPI())
        self.bind_singleton(IBingSuggestion, lambda inj: BingSuggestionAPI())
        
        # Vincula a nova interface à sua implementação Supabase
        self.bind_singleton(IDatabaseRepository, lambda inj: SupabaseRepository())
        
        self.bind_singleton(
            IAutenticadorRewardsService,
            lambda inj: AutenticadorRewards(navegador=inj.get(IRewardsBrowserService)),
        )
        self.bind_singleton(
            INavegadorRewardsService,
            lambda inj: NavegadorRecompensas(navegador=inj.get(IRewardsBrowserService)),
        )
        self.bind_singleton(
            IContaRepository,
            lambda inj: ArquivoContaRepository(inj.get(ExecutorConfig).users_file),
        )
        self.bind_singleton(
            IExecutorEmLoteService,
            lambda inj: ExecutorEmLote(
                bing_search=inj.get(IBingSuggestion),
                conta_repository=inj.get(IContaRepository),
                autenticador=inj.get(IAutenticadorRewardsService),
                perfil_service=inj.get(IPerfilService),
                rewards_data=inj.get(IRewardsDataService),
                logger=inj.get(ILoggingService),
                config=inj.get(ExecutorConfig),
                proxy_service=inj.get(IProxyService),
                # Passa a nova dependência para o executor
                db_repository=inj.get(IDatabaseRepository),
            ),
        )

    # ... (o resto do arquivo permanece o mesmo)
    def bind_instance(self, chave: Type[_T], instancia: _T) -> None:
        self._bindings[chave] = _Binding(factory=lambda _: instancia, singleton=True, instance=instancia, has_instance=True)

    def bind_singleton(self, chave: Type[_T], fabrica: Callable[["SimpleInjector"], _T]) -> None:
        self._bindings[chave] = _Binding(factory=fabrica, singleton=True)

    def bind_factory(self, chave: Type[_T], fabrica: Callable[["SimpleInjector"], _T]) -> None:
        self._bindings[chave] = _Binding(factory=fabrica, singleton=False)

    def get(self, chave: Type[_T]) -> _T:
        if chave not in self._bindings:
            raise KeyError(f"Nenhum binding registrado para {chave!r}")
        binding = self._bindings[chave]
        if binding.singleton:
            if not binding.has_instance:
                binding.instance = binding.factory(self)
                binding.has_instance = True
            return binding.instance
        return binding.factory(self)


def create_injector(config: ExecutorConfig | None = None) -> SimpleInjector:
    """Cria o container padrão da aplicação."""
    return SimpleInjector(config)


__all__ = ["SimpleInjector", "create_injector"]
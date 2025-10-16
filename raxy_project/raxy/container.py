# raxy/container.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Dict, Type, TypeVar

# Interfaces
from raxy.interfaces.repositories import IContaRepository, IDatabaseRepository
from raxy.interfaces.services import (
    IExecutorEmLoteService,
    ILoggingService,
    IRewardsDataService,
    IProxyService,
    IBingSuggestion,
    IBingFlyoutService,
    IMailTmService,
)

# Implementações
from raxy.repositories.file_account_repository import ArquivoContaRepository
from raxy.services.executor_service import ExecutorConfig, ExecutorEmLote
from raxy.services.logging_service import log
from raxy.api.rewards_data_api import RewardsDataAPI
from raxy.api.bing_suggestion_api import BingSuggestionAPI
from raxy.api.supabase_api import SupabaseRepository
from raxy.services.bingflyout_service import BingFlyoutService
from raxy.proxy import Proxy
from raxy.api.mail_tm_api import MailTm
from raxy.domain import InfraServices

_T = TypeVar("_T")


# -------------------------------
# Estrutura interna de Binding
# -------------------------------
@dataclass(slots=True)
class _Binding:
    factory: Callable[[SimpleInjector], Any]
    singleton: bool
    instance: Any = None
    has_instance: bool = False


# -------------------------------
# Injetor de dependências
# -------------------------------
class SimpleInjector:
    def __init__(self, config: ExecutorConfig | None = None) -> None:
        self._bindings: Dict[Type[Any], _Binding] = {}
        self._config = config or ExecutorConfig()
        self._registrar_padrao()

    # -------------------------------
    # Registro de bindings padrão
    # -------------------------------
    def _registrar_padrao(self) -> None:
        self.bind_singleton(IProxyService, lambda inj: Proxy(
            country="US",
            sources=["https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/ss_configs.txt"],
            use_console=True
        ))

        self.bind_instance(ExecutorConfig, self._config)
        self.bind_singleton(ILoggingService, lambda _: log)
        self.bind_singleton(IRewardsDataService, lambda _: RewardsDataAPI())
        self.bind_singleton(IBingSuggestion, lambda _: BingSuggestionAPI())
        self.bind_singleton(IBingFlyoutService, lambda _: BingFlyoutService())
        self.bind_singleton(IDatabaseRepository, lambda _: SupabaseRepository())
        self.bind_singleton(IContaRepository, lambda inj: ArquivoContaRepository(
            inj.get(ExecutorConfig).users_file
        ))
        self.bind_singleton(IMailTmService, lambda _: MailTm())

        # Serviços de infraestrutura
        self.bind_singleton(InfraServices, lambda inj: InfraServices(
            conta_repository=inj.get(IContaRepository),
            rewards_data=inj.get(IRewardsDataService),
            db_repository=inj.get(IDatabaseRepository),
            bing_search=inj.get(IBingSuggestion),
            bing_flyout_service=inj.get(IBingFlyoutService),
            proxy_manager=inj.get(IProxyService),
            logger=inj.get(ILoggingService),
            mail_tm_service=inj.get(IMailTmService),
        ))

        # Executor em lote
        self.bind_singleton(IExecutorEmLoteService, lambda inj: ExecutorEmLote(
            services=inj.get(InfraServices),
            config=inj.get(ExecutorConfig),
        ))

    # -------------------------------
    # Métodos de binding
    # -------------------------------
    def bind_instance(self, chave: Type[_T], instancia: _T) -> None:
        self._bindings[chave] = _Binding(
            factory=lambda _: instancia,
            singleton=True,
            instance=instancia,
            has_instance=True
        )

    def bind_singleton(self, chave: Type[_T], fabrica: Callable[[SimpleInjector], _T]) -> None:
        self._bindings[chave] = _Binding(factory=fabrica, singleton=True)

    def bind_factory(self, chave: Type[_T], fabrica: Callable[[SimpleInjector], _T]) -> None:
        self._bindings[chave] = _Binding(factory=fabrica, singleton=False)

    # -------------------------------
    # Resolução de dependências
    # -------------------------------
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


# -------------------------------
# Função auxiliar
# -------------------------------
def create_injector(config: ExecutorConfig | None = None) -> SimpleInjector:
    return SimpleInjector(config)


__all__ = ["SimpleInjector", "create_injector"]

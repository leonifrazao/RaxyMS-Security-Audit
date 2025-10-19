"""
Sistema de injeção de dependências do Raxy.

Gerencia todas as dependências da aplicação usando um container IoC
(Inversion of Control) simplificado mas eficiente.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Type, TypeVar

# Configuração centralizada
from raxy.core.config import AppConfig, ExecutorConfig, get_config

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
from raxy.services.executor_service import ExecutorEmLote
from raxy.core.logging import get_logger
from raxy.api.rewards_data_api import RewardsDataAPI
from raxy.api.bing_suggestion_api import BingSuggestionAPI
from raxy.api.supabase_api import SupabaseRepository
from raxy.services.bingflyout_service import BingFlyoutService
from raxy.proxy import Proxy
from raxy.api.mail_tm_api import MailTm
from raxy.domain import InfraServices

_T = TypeVar("_T")


@dataclass(slots=True)
class _Binding:
    """
    Binding interno para gerenciamento de dependências.
    
    Attributes:
        factory: Função factory para criar instância
        singleton: Se deve manter única instância
        instance: Instância criada (para singletons)
        has_instance: Flag indicando se instância já foi criada
    """
    factory: Callable[["SimpleInjector"], Any]
    singleton: bool
    instance: Any = None
    has_instance: bool = False


class SimpleInjector:
    """
    Container de injeção de dependências simplificado.
    
    Implementa padrão IoC (Inversion of Control) para gerenciar
    dependências da aplicação de forma centralizada e testável.
    """
    
    def __init__(self, config: AppConfig | None = None) -> None:
        """
        Inicializa o injetor.
        
        Args:
            config: Configuração da aplicação (opcional)
        """
        self._bindings: Dict[Type[Any], _Binding] = {}
        self._config = config or get_config()
        self._registrar_padrao()
    
    def _registrar_padrao(self) -> None:
        """Registra todos os bindings padrão da aplicação."""
        # Configuração
        self.bind_instance(AppConfig, self._config)
        self.bind_instance(ExecutorConfig, self._config.executor)
        
        # Logging
        self.bind_singleton(ILoggingService, lambda _: get_logger())
        
        # Proxies
        self.bind_singleton(IProxyService, lambda inj: Proxy(
            country=inj.get(AppConfig).proxy.country,
            sources=inj.get(AppConfig).proxy.sources,
            use_console=inj.get(AppConfig).proxy.use_console
        ))
        
        # APIs
        self.bind_singleton(IRewardsDataService, lambda _: RewardsDataAPI())
        self.bind_singleton(IBingSuggestion, lambda _: BingSuggestionAPI())
        self.bind_singleton(IBingFlyoutService, lambda _: BingFlyoutService())
        self.bind_singleton(IMailTmService, lambda _: MailTm())
        
        # Repositórios
        self.bind_singleton(IDatabaseRepository, lambda inj: SupabaseRepository(
            url=inj.get(AppConfig).api.supabase_url,
            key=inj.get(AppConfig).api.supabase_key
        ) if inj.get(AppConfig).api.has_supabase else None)
        
        self.bind_singleton(IContaRepository, lambda inj: ArquivoContaRepository(
            inj.get(ExecutorConfig).users_file
        ))

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
            logger=inj.get(ILoggingService),
        ))

    def bind_instance(self, chave: Type[_T], instancia: _T) -> None:
        """
        Registra uma instância específica.
        
        Args:
            chave: Tipo/interface para binding
            instancia: Instância a ser registrada
        """
        self._bindings[chave] = _Binding(
            factory=lambda _: instancia,
            singleton=True,
            instance=instancia,
            has_instance=True
        )
    
    def bind_singleton(self, chave: Type[_T], fabrica: Callable[["SimpleInjector"], _T]) -> None:
        """
        Registra um singleton (instância única).
        
        Args:
            chave: Tipo/interface para binding
            fabrica: Factory function para criar instância
        """
        self._bindings[chave] = _Binding(factory=fabrica, singleton=True)
    
    def bind_factory(self, chave: Type[_T], fabrica: Callable[["SimpleInjector"], _T]) -> None:
        """
        Registra uma factory (nova instância a cada chamada).
        
        Args:
            chave: Tipo/interface para binding
            fabrica: Factory function para criar instâncias
        """
        self._bindings[chave] = _Binding(factory=fabrica, singleton=False)
    
    def get(self, chave: Type[_T]) -> _T:
        """
        Resolve uma dependência.
        
        Args:
            chave: Tipo/interface a resolver
            
        Returns:
            Instância resolvida
            
        Raises:
            KeyError: Se nenhum binding foi registrado
        """
        if chave not in self._bindings:
            raise KeyError(f"Nenhum binding registrado para {chave!r}")
        
        binding = self._bindings[chave]
        
        if binding.singleton:
            if not binding.has_instance:
                binding.instance = binding.factory(self)
                binding.has_instance = True
            return binding.instance
        
        return binding.factory(self)
    
    def has_binding(self, chave: Type) -> bool:
        """
        Verifica se existe binding para o tipo.
        
        Args:
            chave: Tipo/interface a verificar
            
        Returns:
            True se existe binding
        """
        return chave in self._bindings
    
    def clear(self) -> None:
        """Limpa todos os bindings."""
        self._bindings.clear()


def create_injector(config: AppConfig | None = None) -> SimpleInjector:
    """
    Cria um novo injetor de dependências.
    
    Args:
        config: Configuração da aplicação (opcional)
        
    Returns:
        SimpleInjector: Novo injetor configurado
    """
    return SimpleInjector(config)


# Container global (singleton)
_global_injector: SimpleInjector | None = None


def get_injector() -> SimpleInjector:
    """
    Obtém o injetor global.
    
    Returns:
        SimpleInjector: Injetor global
    """
    global _global_injector
    if _global_injector is None:
        _global_injector = create_injector()
    return _global_injector


def reset_injector() -> None:
    """Reseta o injetor global."""
    global _global_injector
    _global_injector = None


__all__ = [
    "SimpleInjector",
    "create_injector",
    "get_injector",
    "reset_injector",
]

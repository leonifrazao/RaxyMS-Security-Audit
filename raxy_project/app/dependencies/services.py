"""Dependências de serviços."""

from __future__ import annotations

from fastapi import Depends, Request

from .core import _get_container as get_injector
from raxy.interfaces.services import (
    IBingSuggestion,
    IBingFlyoutService,
    IExecutorEmLoteService,
    ILoggingService,
    IProxyService,
    IRewardsDataService,
    IMailTmService,
)


def get_proxy_service(request: Request) -> IProxyService:
    """
    Obtém o serviço de proxy.
    
    Args:
        request: Request do FastAPI
        
    Returns:
        IProxyService: Serviço de proxy
    """
    return get_injector(request).get(IProxyService)


def get_logging_service(request: Request) -> ILoggingService:
    """
    Obtém o serviço de logging.
    
    Args:
        request: Request do FastAPI
        
    Returns:
        ILoggingService: Serviço de logging
    """
    return get_injector(request).get(ILoggingService)


def get_rewards_data_service(request: Request) -> IRewardsDataService:
    """
    Obtém o serviço de dados de rewards.
    
    Args:
        request: Request do FastAPI
        
    Returns:
        IRewardsDataService: Serviço de rewards
    """
    return get_injector(request).get(IRewardsDataService)


def get_bing_suggestion_service(request: Request) -> IBingSuggestion:
    """
    Obtém o serviço de sugestões do Bing.
    
    Args:
        request: Request do FastAPI
        
    Returns:
        IBingSuggestion: Serviço de sugestões
    """
    return get_injector(request).get(IBingSuggestion)


def get_executor_service(request: Request) -> IExecutorEmLoteService:
    """
    Obtém o serviço de execução em lote.
    
    Args:
        request: Request do FastAPI
        
    Returns:
        IExecutorEmLoteService: Serviço de execução
    """
    return get_injector(request).get(IExecutorEmLoteService)


def get_mailtm_service(request: Request) -> IMailTmService:
    """
    Obtém o serviço de MailTM.
    
    Args:
        request: Request do FastAPI
        
    Returns:
        IMailTmService: Serviço de MailTM
    """
    return get_injector(request).get(IMailTmService)


def get_bingflyout_service(request: Request) -> IBingFlyoutService:
    """
    Obtém o serviço de Bing Flyout.
    
    Args:
        request: Request do FastAPI
        
    Returns:
        IBingFlyoutService: Serviço de flyout
    """
    return get_injector(request).get(IBingFlyoutService)

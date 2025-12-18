"""Entrada da linha de comando para o Raxy."""

from __future__ import annotations

from raxy.core.config import get_config
from raxy.core.logging import get_logger
from raxy.repositories.file_account_repository import ArquivoContaRepository
from raxy.services.executor_service import ExecutorEmLote
from raxy.services.bingflyout_service import BingFlyoutService
from raxy.api.rewards_data_api import RewardsDataAPI
from raxy.api.bing_suggestion_api import BingSuggestionAPI
from raxy.api.supabase_api import SupabaseRepository
from raxy.proxy.manager import ProxyManager
from raxy.api.mail_tm_api import MailTm


def main() -> None:
    # 1. Configuração
    config = get_config()
    logger = get_logger()
    
    logger.info("Iniciando Raxy...")

    # 2. Repositórios
    conta_repository = ArquivoContaRepository(
        caminho_arquivo=config.executor.users_file
    )
    
    db_repository = None
    if config.api.has_supabase:
        db_repository = SupabaseRepository(
            url=config.api.supabase_url,
            key=config.api.supabase_key
        )

    # 3. Serviços de API e Proxy
    rewards_data = RewardsDataAPI(logger=logger)
    bing_search = BingSuggestionAPI(logger=logger)
    bing_flyout = BingFlyoutService(logger=logger)
    mail_tm = MailTm()
    
    proxy_manager = ProxyManager(
        country=config.proxy.country,
        sources=config.proxy.sources,
        use_console=config.proxy.use_console,
        cache_path=config.get_cache_path(config.proxy.cache_filename)
    )

    # 4. Executor Principal
    executor = ExecutorEmLote(
        rewards_service=rewards_data,
        bing_search_service=bing_search,
        bing_flyout_service=bing_flyout,
        proxy_manager=proxy_manager,
        mail_tm_service=mail_tm,
        conta_repository=conta_repository,
        db_repository=db_repository,
        config=config.executor,
        proxy_config=config.proxy,
        logger=logger
    )

    # 7. Execução
    executor.executar()


if __name__ == "__main__":
    main()

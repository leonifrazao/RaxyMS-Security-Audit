from dataclasses import dataclass
from raxy.interfaces.repositories import IContaRepository, IDatabaseRepository
from raxy.interfaces.services import (
    ILoggingService,
    IRewardsDataService,
    IBingSuggestion,
    IBingFlyoutService,
    IProxyService,
    IMailTmService,
    IDashboardService
)


@dataclass
class InfraServices:
    conta_repository: IContaRepository
    rewards_data: IRewardsDataService
    db_repository: IDatabaseRepository
    bing_search: IBingSuggestion
    bing_flyout_service: IBingFlyoutService
    proxy_manager: IProxyService
    logger: ILoggingService
    mail_tm_service: IMailTmService
    dashboard: IDashboardService


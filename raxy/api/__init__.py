"""APIs públicas do Microsoft Rewards."""

from .bing_search_api import BingSearchAPI
from .rewards_tasks import RewardsTasksAPI
from .rewards_data_api import RewardsDataAPI

__all__ = [
    "RewardsTasksAPI",
    "BingSearchAPI",
    "RewardsDataAPI",
    "ProxyAPI",
]

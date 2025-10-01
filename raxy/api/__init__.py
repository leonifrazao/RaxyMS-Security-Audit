"""APIs públicas do Microsoft Rewards."""

from .bing_search_api import BingSearchAPI
from .rewards_api import APIRecompensas, TemplateRequester
from .rewards_data_api import RewardsDataAPI

__all__ = [
    "APIRecompensas",
    "BingSearchAPI",
    "RewardsDataAPI",
    "TemplateRequester",
    "ProxyAPI",
]

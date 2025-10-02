"""APIs públicas do Microsoft Rewards."""

from .bing_suggestion_api import BingSuggestionAPI
from .rewards_data_api import RewardsDataAPI

__all__ = [
    "BingSuggestionAPI",
    "RewardsDataAPI",
    "ProxyAPI",
]

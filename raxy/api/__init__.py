"""APIs públicas do Microsoft Rewards."""

from .rewards_api import APIRecompensas, TemplateRequester
from .rewards_data_api import RewardsDataAPI
from .proxy.proxy import ProxyAPI

__all__ = [
    "APIRecompensas",
    "RewardsDataAPI",
    "TemplateRequester",
    "ProxyAPI",
]

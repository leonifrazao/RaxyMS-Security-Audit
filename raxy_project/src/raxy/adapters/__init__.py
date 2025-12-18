"""
Adapters Module

Contains:
- api: External API clients (Bing, MailTM, Rewards, Supabase)
- repositories: Data persistence
- http: HTTP client implementations
"""

from raxy.adapters.api.base_api import BaseAPIClient
from raxy.adapters.api.bing_suggestion_api import BingSuggestionAPI
from raxy.adapters.api.rewards_data_api import RewardsDataAPI
from raxy.adapters.api.mail_tm_api import MailTm

__all__ = [
    "BaseAPIClient",
    "BingSuggestionAPI",
    "RewardsDataAPI",
    "MailTm",
]

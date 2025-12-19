"""APIs públicas do Microsoft Rewards."""

from .bing_suggestion_api import BingSuggestionAPI
from .rewards_data_api import RewardsDataAPI
from .supabase_api import SupabaseRepository
from .mail_tm_api import MailTm

__all__ = [
    "BingSuggestionAPI",
    "RewardsDataAPI",
    "ProxyAPI",
    "SupabaseRepository",
    "MailTm",
]
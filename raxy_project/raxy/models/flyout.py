from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class FlyoutResult:
    """Represents the result of extracting data from the Bing Rewards flyout."""
    user_id: str
    offer_id: str
    auth_key: str
    sku: str
    conta_bugada: bool = False
    bug_detalhes: str = ""

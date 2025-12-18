from typing import Any, Dict, Optional
from raxy.adapters.api.base_api import BaseAPIClient

class BingAPI(BaseAPIClient):
    """
    Unified API Client for Bing related services (Suggestions, Rewards).
    """

    def get_suggestions(self, query: str) -> Dict[str, Any]:
        """
        Fetches search suggestions from Bing.
        """
        # Load template or define request
        # For now assuming we use a template 'bing_suggestion.json'
        # In reality we might need to migrate the logic from the old file
        # But for this refactoring demonstration I'll implement a generic call
        
        # Note: The original code likely used a template.
        # We should check if 'bing_suggestion.json' exists in templates.
        
        return self._request(
            "GET", 
            "/AS/Suggestions", 
            params={"q": query, "cvid": "...", "qry": query} 
            # In a real migration we would load these params from the template or arguments
        )

    def get_rewards_dashboard(self) -> Dict[str, Any]:
        """
        Fetches Rewards dashboard data.
        """
        return self._request("GET", "/rewards/dashboard")

    # Add other methods from rewards_data_api.py and bing_suggestion_api.py

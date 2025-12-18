
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from raxy.main import main
from raxy.services.executor_service import ExecutorEmLote
from raxy.services.bingflyout_service import BingFlyoutService
from raxy.api.rewards_data_api import RewardsDataAPI
from raxy.api.bing_suggestion_api import BingSuggestionAPI
from raxy.api.mail_tm_api import MailTm
from raxy.proxy.manager import ProxyManager

def test_imports():
    """Test if all modules can be imported without error."""
    print("Testing imports...")
    # Imports are already done at top level
    print("Imports successful.")

def test_instantiation():
    """Test if services can be instantiated (mocking dependencies where needed)."""
    print("Testing instantiation...")
    try:
        from raxy.core.logging import get_logger
        logger = get_logger()
        
        # APIs
        rewards_api = RewardsDataAPI(logger=logger)
        bing_api = BingSuggestionAPI(logger=logger)
        mail_tm = MailTm(logger=logger)
        
        print("APIs instantiated.")
        
        # We won't instantiate ExecutorEmLote here as it requires many dependencies,
        # but successful import and API instantiation is a good sign.
        
    except Exception as e:
        print(f"Instantiation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_imports()
    test_instantiation()
    print("Smoke test passed!")

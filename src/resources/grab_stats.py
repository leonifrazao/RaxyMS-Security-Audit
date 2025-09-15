from botasaurus.browser import browser, Driver

from .config import BROWSER_KWARGS


@browser(**{**BROWSER_KWARGS, "reuse_driver": True})
def goto_rewards_page(driver: Driver, data) -> None:
    """Open the Bing Rewards page with human-mode enabled."""
    driver.enable_human_mode()
    driver.google_get("https://rewards.bing.com")

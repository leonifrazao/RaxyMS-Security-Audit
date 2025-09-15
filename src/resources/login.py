import os
from typing import Mapping, Any

from botasaurus.browser import browser, Driver, Wait

from .config import BROWSER_KWARGS


@browser(**BROWSER_KWARGS)
def login(driver: Driver, data: Mapping[str, Any] | None = None) -> None:
    """Perform Microsoft Rewards login flow.

    Credentials are read from `data` (keys: `email`, `password`) or
    environment variables `MS_EMAIL` and `MS_PASSWORD`.
    """
    # Read credentials
    data = data or {}
    email = (data.get("email") or os.getenv("MS_EMAIL") or "").strip()
    password = (data.get("password") or os.getenv("MS_PASSWORD") or "").strip()

    driver.enable_human_mode()
    driver.google_get("https://www.microsoft.com/pt-br/rewards/about")
    driver.click("a[id='mectrl_main_trigger']", wait=Wait.VERY_LONG)
    driver.short_random_sleep()

    if not email or not password:
        # Fail fast with a clear message; botasaursus will capture logs
        raise ValueError("Credenciais ausentes: defina MS_EMAIL/MS_PASSWORD ou passe em data={}")

    driver.type("input[type='email']", email, wait=Wait.VERY_LONG)
    driver.click("input[type='submit']")
    driver.short_random_sleep()
    driver.type("input[type='password']", password, wait=Wait.VERY_LONG)
    driver.click("button[type='submit']")
    driver.short_random_sleep()
    try:
        driver.click("button[type='submit']", wait=Wait.SHORT)
    except Exception:
        # Optional confirm prompt may not appear
        pass

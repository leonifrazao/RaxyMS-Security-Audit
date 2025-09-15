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
    # Bypass Acess Denied
    driver.google_get("https://rewards.bing.com")
    # driver.click("a[id='mectrl_main_trigger']", wait=Wait.VERY_LONG)
    driver.short_random_sleep()
    # Já esta logado
    if driver.is_element_present("h1[ng-bind-html='$ctrl.nameHeader']", wait=Wait.VERY_LONG):
        return

    if not email or not password:
        # Fail fast with a clear message; botasaursus will capture logs
        raise ValueError("Credenciais ausentes: defina MS_EMAIL/MS_PASSWORD ou passe em data={}")

    driver.type("input[type='email']", email, wait=Wait.VERY_LONG)
    driver.click("button[type='submit']")
    driver.short_random_sleep()
    driver.type("input[type='password']", password, wait=Wait.VERY_LONG)
    driver.click("button[type='submit']")
    driver.short_random_sleep()
    driver.prompt()
    try:
        # driver.wait_for_element("button[type='submit', aria-label='Yes']", wait=Wait.VERY_LONG)
        # Selector correto para salvar login
        driver.click("button[aria-label='Yes']", wait=Wait.SHORT)
    except Exception:
        # Optional confirm prompt may not appear
        pass

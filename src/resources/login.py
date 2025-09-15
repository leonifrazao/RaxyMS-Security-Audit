from botasaurus.browser import browser, Driver
from botasaurus.profiles import Profiles
from botasaurus.browser import Wait

from .utils import set_profile

@browser(
    remove_default_browser_check_argument=True,
    wait_for_complete_page_load=True,
    block_images=True,
    output=None,
    tiny_profile=True
)
def login(driver: Driver, data):
    # Visit the website via Google Referrer
    driver.enable_human_mode()
    driver.google_get("https://www.microsoft.com/pt-br/rewards/about")
    driver.click("a[id='mectrl_main_trigger']", wait=Wait.VERY_LONG)
    driver.short_random_sleep()
    driver.type("input[type='email']", "fodasekakakaka1@outlook.com", wait=Wait.VERY_LONG)
    driver.click("input[type='submit']")  # Click an element
    driver.short_random_sleep()
    driver.type("input[type='password']", "aksjdashdasdddddd1111", wait=Wait.VERY_LONG)
    driver.click("button[type='submit']")  # Click an element
    driver.short_random_sleep()
    try:
        driver.click("button[type='submit']", wait=Wait.SHORT)  # Click an element
    except:
        pass

if __name__ == "__main__":
    set_profile("jhasdjhkashjk")
    login(
        profile="jhasdjhkashjk",
        tiny_profile=True, 
        remove_default_browser_check_argument=True,
        add_arguments=[f'--user-agent={Profiles.get_profile("jhasdjhkashjk")["UA"]}'],
    )
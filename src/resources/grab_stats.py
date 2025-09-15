from botasaurus.browser import browser, Driver
from botasaurus.profiles import Profiles
from botasaurus.browser import Wait

from .utils import set_profile

@browser(
    remove_default_browser_check_argument=True,
    wait_for_complete_page_load=True,
    block_images=True,
    output=None,
    reuse_driver=True,
    tiny_profile=True, 
)
def goto_rewards_page(driver: Driver, data):
    # Visit the website via Google Referrer
    driver.enable_human_mode()
    driver.google_get("https://rewards.bing.com")
    
if __name__ == "__main__":
    set_profile("jhasdjhkashjk")
    goto_rewards_page(
        profile="jhasdjhkashjk",
        tiny_profile=True, 
        remove_default_browser_check_argument=True,
        add_arguments=[f'--user-agent={Profiles.get_profile("jhasdjhkashjk")["UA"]}'],
    )
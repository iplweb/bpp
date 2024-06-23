import time

from selenium.webdriver.support.expected_conditions import staleness_of
from selenium.webdriver.support.ui import WebDriverWait

VERY_SHORT_WAIT_TIME = 1
SHORT_WAIT_TIME = 5
LONG_WAIT_TIME = 10
DEFAULT_WAIT_TIME = SHORT_WAIT_TIME
PAGE_LOAD_WAIT_TIME = LONG_WAIT_TIME


def wait_for(condition_function, max_seconds=DEFAULT_WAIT_TIME):
    start_time = time.time()
    while time.time() < start_time + max_seconds:
        if condition_function():
            return True
        else:
            time.sleep(0.1)
    raise TimeoutError(f"Timeout waiting for {condition_function.__name__}")


class wait_for_page_load:
    def __init__(self, browser, max_seconds=PAGE_LOAD_WAIT_TIME):
        self.browser = browser
        self.max_seconds = max_seconds

    def __enter__(self):

        self.old_page = self.browser.find_by_tag("html").first._element

    def __exit__(self, *_):
        WebDriverWait(self.browser, self.max_seconds).until(
            lambda x: staleness_of(self.old_page)
        )

        WebDriverWait(self.browser, self.max_seconds).until(
            lambda browser: browser.execute_script("return document.readyState")
            == "complete"
        )

        WebDriverWait(self.browser, self.max_seconds).until(
            lambda browser: not browser.find_by_tag("body").is_empty()
        )


def wait_for_websocket_connection(browser):
    WebDriverWait(browser, DEFAULT_WAIT_TIME).until(
        lambda browser: browser.execute_script(
            "return bppNotifications.chatSocket.readyState"
        )
        == 1
    )

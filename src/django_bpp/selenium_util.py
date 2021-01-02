# -*- encoding: utf-8 -*-
import time

from selenium.webdriver.support.expected_conditions import staleness_of
from selenium.webdriver.support.ui import WebDriverWait


def wait_for(condition_function):
    start_time = time.time()
    while time.time() < start_time + 10:
        if condition_function():
            return True
        else:
            time.sleep(0.1)
    raise TimeoutError("Timeout waiting for {}".format(condition_function.__name__))


class wait_for_page_load(object):
    def __init__(self, browser):
        self.browser = browser

    def __enter__(self):
        self.old_page = self.browser.find_by_tag("html")[0]._element

    def __exit__(self, *_):
        WebDriverWait(self.browser, 10).until(lambda x: staleness_of(self.old_page))

        WebDriverWait(self.browser, 10).until(
            lambda browser: browser.execute_script("return document.readyState")
            == "complete"
        )


def wait_for_websocket_connection(browser):
    WebDriverWait(browser, 10).until(
        lambda browser: browser.execute_script(
            "return bppNotifications.chatSocket.readyState"
        )
        == 1
    )

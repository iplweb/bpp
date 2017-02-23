import time


def wait_for_object(klass, pk, no_tries=10, called_by=""):
    obj = None

    while no_tries > 0:
        try:
            obj = klass.objects.get(pk=pk)
            break
        except klass.DoesNotExist:
            time.sleep(1)
            no_tries = no_tries - 1

    if obj is None:
        raise klass.DoesNotExist("Cannot fetch klass %r with pk %r, TB: %r" % (klass, pk, called_by))

    return obj


def wait_for(condition_function):
    start_time = time.time()
    while time.time() < start_time + 10:
        if condition_function():
            return True
        else:
            time.sleep(0.1)
    raise Exception(
        'Timeout waiting for {}'.format(condition_function.__name__)
    )


from selenium.webdriver.support.expected_conditions import staleness_of
from selenium.webdriver.support.ui import WebDriverWait


class wait_for_page_load(object):
    def __init__(self, browser):
        self.browser = browser

    def __enter__(self):
        self.old_page = self.browser.find_by_tag('html')[0]._element

    def __exit__(self, *_):
        WebDriverWait(self.browser, 10).until(
            staleness_of(self.old_page)
        )

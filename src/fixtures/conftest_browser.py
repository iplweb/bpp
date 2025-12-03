"""Browser and Selenium fixtures."""

import pytest
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django_webtest import DjangoTestApp
from splinter.driver import DriverAPI

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

import django_webtest
import webtest

from django_bpp.selenium_util import wait_for_page_load, wait_for_websocket_connection

NORMAL_DJANGO_USER_LOGIN = "test_login_bpp"
NORMAL_DJANGO_USER_PASSWORD = "test_password"


@pytest.fixture
def normal_django_user(request, db, django_user_model):
    """A normal Django user"""
    try:
        obj = django_user_model.objects.get(username=NORMAL_DJANGO_USER_LOGIN)
    except django_user_model.DoesNotExist:
        obj = django_user_model.objects.create_user(
            username=NORMAL_DJANGO_USER_LOGIN, password=NORMAL_DJANGO_USER_PASSWORD
        )

    def fin():
        obj.delete()

    return obj


def _preauth_session_id_helper(
    username,
    password,
    client,
    browser,
    channels_live_server,  # noqa
    django_user_model,
    django_username_field,
):
    res = client.login(username=username, password=password)
    assert res is True

    with wait_for_page_load(browser):
        browser.visit(channels_live_server.url + "/non-existant-url")
    browser.cookies.add({"sessionid": client.cookies["sessionid"].value})
    browser.authorized_user = django_user_model.objects.get(
        **{django_username_field: username}
    )
    return browser


@pytest.fixture
def splinter_browser(request, browser_instance_getter):
    return browser_instance_getter(request, splinter_browser)


@pytest.fixture
def preauth_browser(
    normal_django_user,
    client,
    splinter_browser,
    channels_live_server,  # noqa
    django_user_model,
    django_username_field,
):
    browser = _preauth_session_id_helper(
        NORMAL_DJANGO_USER_LOGIN,
        NORMAL_DJANGO_USER_PASSWORD,
        client,
        splinter_browser,
        channels_live_server,
        django_user_model,
        django_username_field,
    )

    yield browser
    browser.quit()


@pytest.fixture
def preauth_asgi_browser(
    preauth_browser,
    transactional_db,
    channels_live_server,  # noqa
):
    with wait_for_page_load(preauth_browser):
        preauth_browser.visit(channels_live_server.url)
    wait_for_websocket_connection(preauth_browser)
    return preauth_browser


@pytest.fixture
def admin_browser(
    admin_user,
    client,
    splinter_browser,
    channels_live_server,  # noqa
    django_user_model,
    django_username_field,
    transactional_db,
) -> DriverAPI:
    from selenium.webdriver.support.ui import WebDriverWait

    browser = _preauth_session_id_helper(
        "admin",
        "password",
        client,
        splinter_browser,
        channels_live_server,
        django_user_model,
        django_username_field,
    )
    browser.driver.set_window_size(1920, 1600)

    # Wrap the visit method to wait for full page load including FOUC prevention
    original_visit = browser.visit

    def visit_with_wait(url):
        original_visit(url)
        # Wait for page to be fully loaded
        WebDriverWait(browser.driver, 10).until(
            lambda driver: driver.execute_script("return document.readyState")
            == "complete"
        )
        # Wait for FOUC prevention to complete (html element becomes visible)
        # base_site.html sets html visibility:hidden and opacity:0, then shows it after load
        WebDriverWait(browser.driver, 10).until(
            lambda driver: driver.execute_script(
                """
                var html = document.documentElement;
                var style = window.getComputedStyle(html);
                return style.visibility === 'visible' && parseFloat(style.opacity) > 0;
                """
            )
        )

    browser.visit = visit_with_wait

    # Add helper method to wait for element to be interactable
    def wait_for_interactable(css_selector, timeout=10):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC

        element = WebDriverWait(browser.driver, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, css_selector))
        )
        return element

    browser.wait_for_interactable = wait_for_interactable

    yield browser
    browser.execute_script("window.onbeforeunload = function(e) {};")
    browser.quit()


@pytest.fixture(scope="function")
def webtest_app(request):
    wtm = django_webtest.WebTestMixin()
    wtm._patch_settings()
    request.addfinalizer(wtm._unpatch_settings)
    return django_webtest.DjangoTestApp()


def _webtest_login(webtest_app, username, password, login_form="login_form"):
    if apps.is_installed("microsoft_auth"):
        if username != "admin":
            raise ImproperlyConfigured(
                "Prawdopodobnie próbujesz zalogować zwykłego użytkownika przez panel "
                "admina. Jednocześnie jest właczone microsoft_auth. To logowanie się nie powiedzie -"
                " funkcja testowa musiałaby wciągnąć w test cały serwer Microsoftu. Wyłącz "
                "microsoft_auth i uruchom ten test ponownie. "
            )

        # Nie używamy parametru login_form, logujemy hasłem przez admina. Czemu?
        # temu, że przy włączonej autoryzacji microsoft_auth, ten formularz login_form
        # nie będzie w ogóle dostępny w drzewku URLi (mpasternak, 12.10.2023)
        form = webtest_app.get(reverse("admin:login")).form
    else:
        form = webtest_app.get(reverse(login_form)).form

    form["username"] = username
    form["password"] = password
    res = form.submit().maybe_follow()

    assert res.context["user"].username == username
    return webtest_app


@pytest.fixture(scope="function")
def wprowadzanie_danych_user(normal_django_user):
    from django.contrib.auth.models import Group

    from bpp import const

    # zeby bpp.core.editor_emails zwracało
    normal_django_user.email = "foo@bar.pl"

    grp = Group.objects.get_or_create(name=const.GR_WPROWADZANIE_DANYCH)[0]
    normal_django_user.groups.add(grp)

    normal_django_user.save()
    return normal_django_user


@pytest.fixture(scope="function")
def app(webtest_app, normal_django_user) -> webtest.app.TestApp:
    return _webtest_login(
        webtest_app, NORMAL_DJANGO_USER_LOGIN, NORMAL_DJANGO_USER_PASSWORD
    )


@pytest.fixture(scope="function")
def wd_app(webtest_app, wprowadzanie_danych_user):
    return _webtest_login(
        webtest_app, NORMAL_DJANGO_USER_LOGIN, NORMAL_DJANGO_USER_PASSWORD
    )


@pytest.fixture(scope="function")
def admin_app(webtest_app, admin_user) -> DjangoTestApp:
    """
    :rtype: django_webtest.DjangoTestApp
    """
    return _webtest_login(webtest_app, "admin", "password")


@pytest.fixture
def csrf_exempt_django_admin_app(django_app_factory, admin_user):
    app = django_app_factory(csrf_checks=False)
    return _webtest_login(app, "admin", "password")


# https://github.com/pytest-dev/pytest-splinter/issues/158
#  AttributeError: module 'splinter.driver.webdriver.firefox' has no attribute 'WebDriverElement'


@pytest.fixture(scope="session")
def browser_patches():
    from pytest_splinter.webdriver_patches import patch_webdriver

    patch_webdriver()

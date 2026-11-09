"""Browser and webtest fixtures."""

import django_webtest
import pytest
import webtest
from django_webtest import DjangoTestApp

from .const import NORMAL_DJANGO_USER_LOGIN, NORMAL_DJANGO_USER_PASSWORD


@pytest.fixture
def normal_django_user(db, django_user_model):
    """A normal Django user"""
    # Fikstura jest function-scoped na `db` — pytest-django rolluje back
    # transakcję po teście, więc ręczny teardown (usuwanie usera) jest
    # zbędny. Wcześniejszy lokalny `fin()` nigdy nie był rejestrowany
    # przez `request.addfinalizer`, więc był martwym kodem — usunięty.
    try:
        obj = django_user_model.objects.get(username=NORMAL_DJANGO_USER_LOGIN)
    except django_user_model.DoesNotExist:
        obj = django_user_model.objects.create_user(
            username=NORMAL_DJANGO_USER_LOGIN, password=NORMAL_DJANGO_USER_PASSWORD
        )

    return obj


@pytest.fixture(scope="function")
def webtest_app(request):
    wtm = django_webtest.WebTestMixin()
    wtm._patch_settings()
    request.addfinalizer(wtm._unpatch_settings)
    return django_webtest.DjangoTestApp()


def _webtest_login(webtest_app, username, password):
    """Zaloguj ``webtest_app`` jako ``username``.

    Zamiast przechodzić formularz logowania (GET formularza + POST +
    przekierowanie na stronę startową = 3 pełne requesty na KAŻDY test
    z ``admin_app``/``wd_app``) tworzymy sesję przez ``Client.force_login``
    i przekazujemy jej ciasteczko do webtesta. ``force_login`` woła
    ``django.contrib.auth.login``, więc sygnał ``user_logged_in`` i rotacja
    sesji działają jak przy zwykłym logowaniu. Sam formularz logowania
    testują osobne testy (``bpp/tests/test_views/test_auth.py`` i in.).
    """
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.test import Client

    user = get_user_model().objects.get(username=username)
    # Fikstury podają hasło — pilnujemy, że jest prawdziwe, jak formularz.
    assert user.check_password(password), f"złe hasło testowe dla {username}"

    client = Client()
    client.force_login(user)
    webtest_app.set_cookie(
        settings.SESSION_COOKIE_NAME,
        client.cookies[settings.SESSION_COOKIE_NAME].value,
    )
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


@pytest.fixture
def csrf_exempt_wd_app(django_app_factory, wprowadzanie_danych_user):
    app = django_app_factory(csrf_checks=False)
    return _webtest_login(app, NORMAL_DJANGO_USER_LOGIN, NORMAL_DJANGO_USER_PASSWORD)

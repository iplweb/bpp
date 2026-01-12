"""Browser and Selenium fixtures."""

import pytest
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django_webtest import DjangoTestApp

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

import django_webtest
import webtest

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

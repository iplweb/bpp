# -*- encoding: utf-8 -*-


from django.core.management import call_command

#
# # SPRAWDZE czy
# # - HTML wysyłany przechodzi
# # - odwiedzenie URLa powoduje zamykanie komunkatu
# celery always eager dla testów pytest w conftest
# - czy to ruszy sprawdze
# # - klikniecie "generuj raport" powoduje wygenerowanie komunikatu
#
# CO DALEJ W DJANGO_BPP
#
# * cssClass w chwili dodawania komunikatu via offline tool,
# * close URL j/w
#
# POTEM AUTORYZACJA JAKAS MOZE na te komunikaty
# tzn. najbardziej to na WYSYLANIE by sie przydala.


try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

import pytest
from selenium.webdriver.support.wait import WebDriverWait

from conftest import NORMAL_DJANGO_USER_PASSWORD

from bpp.models.system import Charakter_Formalny, Jezyk, Status_Korekty, Typ_KBN

from django_bpp.selenium_util import SHORT_WAIT_TIME, wait_for_page_load

pytestmark = [pytest.mark.slow, pytest.mark.selenium]


def test_caching_enabled(
    admin_app, zrodlo, standard_data, transactional_db, with_cache
):
    """
    1) wejdź do redagowania
    2) dopisz publikację, zapisz
    3) wejdź do multiseeka
    4) sprawdź, czy jest widoczny tytuł na liście po wybraniu wyszukiwania

    -- dla DOMYSLNEJ konfiguracji, cache powinno byc uruchomione przez appconfig,
    celery powinno w trybie always_eager wrzucac cache'owany opis publikacji
    """
    page = admin_app.get(reverse("admin:bpp_wydawnictwo_ciagle_add"))

    #  char = Charakter_Formalny.objects.get_or_create(nazwa="charakter", skrot="chr")[0]

    form = page.forms[1]
    form["tytul_oryginalny"].value = "Takie tam"
    form["rok"].value = "2000"

    form["zrodlo"].force_value(
        [
            zrodlo.pk,
        ]
    )  # force_value bo to autocomplete
    form["charakter_formalny"].value = Charakter_Formalny.objects.all().first().pk
    form["jezyk"].value = Jezyk.objects.all().first().pk
    form["typ_kbn"].value = Typ_KBN.objects.all().first().pk
    form["status_korekty"].value = Status_Korekty.objects.all().first().pk
    form.submit()

    # Teraz wchodzimy do multiseek i sprawdzamy jak to wyglada

    page = admin_app.get(reverse("multiseek:results"))

    found = False
    for elem in page.html.find_all("a", href=True):
        if elem["href"].find("/bpp/rekord/") == 0:
            assert "Takie tam" in elem.text
            found = True

    assert found


def test_live_server(live_server, browser):
    browser.visit(live_server.url)
    assert "Wystąpił błąd" not in browser.html


@pytest.mark.django_db(transaction=True)
def test_asgi_live_server(preauth_asgi_browser):

    s = "test notyfikacji 123 456"
    call_command(
        "send_notification",
        preauth_asgi_browser.authorized_user.username,
        s,
        verbosity=0,
    )

    WebDriverWait(preauth_asgi_browser, SHORT_WAIT_TIME).until(
        lambda browser: browser.is_text_present(s)
    )


def test_bpp_notifications(preauth_asgi_browser):
    """Sprawdz, czy notyfikacje dochodza.
    Wymaga uruchomionego staging-server.
    """
    s = "test notyfikacji 123 456"
    assert preauth_asgi_browser.is_text_not_present(s)
    call_command(
        "send_notification",
        preauth_asgi_browser.authorized_user.username,
        s,
        verbosity=0,
    )
    assert preauth_asgi_browser.is_text_present(s)


def test_bpp_notifications_and_messages(preauth_asgi_browser):
    """Sprawdz, czy notyfikacje dochodza. """

    s = "test notyfikacji 123 456 902309093209092"
    assert preauth_asgi_browser.is_text_not_present(s)

    call_command("send_message", preauth_asgi_browser.authorized_user.username, s)

    WebDriverWait(preauth_asgi_browser, SHORT_WAIT_TIME).until(
        lambda browser: browser.is_text_present(s)
    )

    with wait_for_page_load(preauth_asgi_browser):
        preauth_asgi_browser.reload()

    WebDriverWait(preauth_asgi_browser, SHORT_WAIT_TIME).until(
        lambda browser: browser.is_text_present(s)
    )


def test_preauth_browser(preauth_browser, live_server):
    """Sprawdz, czy pre-autoryzowany browser zwyklego uzytkownika
    funkcjonuje poprawnie."""
    preauth_browser.visit(live_server + "/admin/")
    assert preauth_browser.is_text_present(u"Login") or preauth_browser.is_text_present(
        u"Zaloguj si"
    )


def test_admin_browser(admin_browser, asgi_live_server):
    """Sprawdz, czy pre-autoryzowany browser admina funkcjonuje poprawnie"""
    admin_browser.visit(asgi_live_server.url + "/admin/")
    assert admin_browser.is_text_present(u"Administracja stron")


def test_webtest(webtest_app, normal_django_user):
    form = webtest_app.get(reverse("login_form")).form
    form["username"] = normal_django_user.username
    form["password"] = NORMAL_DJANGO_USER_PASSWORD
    res = form.submit().follow()
    assert res.context["user"].username == normal_django_user.username

import time

from django.core.management import call_command

#
# # SPRAWDZE czy
# # - HTML wysyłany przechodzi
# # - odwiedzenie URLa powoduje zamykanie komunkatu
# celery always eager dla testów pytest w fixtures
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
from playwright.sync_api import Page, expect

from bpp.models.system import Charakter_Formalny, Jezyk, Status_Korekty, Typ_KBN
from django_bpp.playwright_util import wait_for_page_load
from fixtures import NORMAL_DJANGO_USER_PASSWORD

pytestmark = [pytest.mark.slow]


def test_caching_enabled(
    admin_app,
    zrodlo,
    standard_data,
    transactional_db,
    denorms,
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

    form = page.forms["wydawnictwo_ciagle_form"]
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

    time.sleep(1)

    denorms.flush()

    # Teraz wchodzimy do multiseek i sprawdzamy jak to wyglada

    page = admin_app.get(reverse("multiseek:results"))

    found = False
    for elem in page.html.find_all("a", href=True):
        if elem["href"].find("/bpp/rekord/") == 0:
            assert "Takie tam" in elem.text
            found = True

    assert found


@pytest.mark.serial
def test_live_server(live_server, page: Page):
    page.goto(live_server.url)
    expect(page.locator("body")).not_to_contain_text("Wystąpił błąd")


@pytest.mark.django_db(transaction=True)
def test_channels_live_server(preauth_asgi_page: Page):
    s = "test notyfikacji 123 456"

    page = preauth_asgi_page

    page.wait_for_timeout(500)

    call_command(
        "send_notification",
        preauth_asgi_page.authorized_user.username,
        s,
        verbosity=0,
    )

    page.wait_for_function(
        f"() => document.body.textContent.includes('{s}')", timeout=1000
    )


@pytest.mark.django_db(transaction=True)
def test_bpp_notifications(preauth_asgi_page: Page):
    """Sprawdz, czy notyfikacje dochodza.
    Wymaga uruchomionego staging-server.
    """
    s = "test notyfikacji 123 456"
    page = preauth_asgi_page
    expect(page.locator("body")).not_to_contain_text(s)
    call_command(
        "send_notification",
        preauth_asgi_page.authorized_user.username,
        s,
        verbosity=0,
    )
    # Give time for notification to arrive
    page.wait_for_timeout(1000)
    expect(page.locator("body")).to_contain_text(s, timeout=15000)


def test_bpp_notifications_and_messages(preauth_asgi_page: Page):
    """Sprawdz, czy notyfikacje dochodza."""

    s = "test notyfikacji 123 456 902309093209092"
    page = preauth_asgi_page
    expect(page.locator("body")).not_to_contain_text(s)

    call_command("send_message", preauth_asgi_page.authorized_user.username, s)

    page.wait_for_timeout(1000)  # Give time for message to be sent
    page.wait_for_function(
        f"() => document.body.textContent.includes('{s}')", timeout=15000
    )

    page.reload()
    wait_for_page_load(page)

    page.wait_for_function(
        f"() => document.body.textContent.includes('{s}')", timeout=15000
    )


def test_preauth_browser(preauth_page: Page, live_server):
    """Sprawdz, czy pre-autoryzowany browser zwyklego uzytkownika
    funkcjonuje poprawnie."""
    page = preauth_page
    page.goto(live_server.url + "/admin/")
    page_content = page.content()
    assert "Login" in page_content or "Zaloguj si" in page_content


@pytest.mark.django_db
def test_admin_browser(admin_page: Page, channels_live_server):
    """Sprawdz, czy pre-autoryzowany browser admina funkcjonuje poprawnie"""
    page = admin_page
    page.goto(channels_live_server.url + "/admin/")
    expect(page.locator("body")).to_contain_text("Panel Sterowania")


@pytest.mark.uruchom_tylko_bez_microsoft_auth
@pytest.mark.django_db
def test_webtest(webtest_app, normal_django_user):
    form = webtest_app.get(reverse("login_form")).form
    form["username"] = normal_django_user.username
    form["password"] = NORMAL_DJANGO_USER_PASSWORD
    res = form.submit().follow()
    assert res.context["user"].username == normal_django_user.username

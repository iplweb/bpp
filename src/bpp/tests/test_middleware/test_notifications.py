"""Testy `NotificationsMiddleware` — semantyka + koszt zapytań.

Middleware oznacza trwałe wiadomości `messages_extends` jako przeczytane,
gdy user odwiedzi URL cytowany w treści wiadomości. Dopasowanie jest przez
``message__icontains`` (LIKE '%...%'), czyli pełny skan tabeli wiadomości —
dlatego wolno je wykonać dopiero po tanim sprawdzeniu, czy user w ogóle ma
cokolwiek nieprzeczytanego.
"""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from messages_extends.constants import INFO_PERSISTENT
from messages_extends.models import Message

from bpp.middleware import NotificationsMiddleware


def _przetworz(request):
    NotificationsMiddleware(lambda r: None).process_request(request)


def _utworz_wiadomosc(user, tresc):
    return Message.objects.create(
        user=user, message=tresc, level=INFO_PERSISTENT, read=False
    )


@pytest.fixture
def request_na_url():
    def _make(user, url="/lista/publikacji/"):
        request = RequestFactory().get(url)
        request.user = user
        return request

    return _make


@pytest.mark.django_db
def test_anonim_nie_odpytuje_bazy(request_na_url, django_assert_num_queries):
    """Niezalogowany user nie generuje ŻADNEGO zapytania."""
    request = request_na_url(AnonymousUser())
    with django_assert_num_queries(0):
        _przetworz(request)


@pytest.mark.django_db
def test_user_bez_nieprzeczytanych_nie_wykonuje_update(admin_user, request_na_url):
    """Brak nieprzeczytanych → żadnego UPDATE, tylko tani odczyt.

    Sedno optymalizacji: dla zdecydowanej większości requestów (user nie ma
    trwałych wiadomości) middleware nie może wykonywać zapisu z ``icontains``,
    który jest pełnym skanem tabeli wiadomości. Liczba zapytań tego NIE
    wykazuje — stary kod też robił dokładnie jedno — więc sprawdzamy rodzaj.
    """
    request = request_na_url(admin_user)

    with CaptureQueriesContext(connection) as ctx:
        _przetworz(request)

    zapytania = [q["sql"] for q in ctx.captured_queries]
    assert not any(
        "UPDATE" in sql.upper() for sql in zapytania
    ), f"Middleware wykonał zapis mimo braku nieprzeczytanych: {zapytania}"
    assert len(zapytania) <= 1, f"Oczekiwano najwyżej 1 zapytania: {zapytania}"


@pytest.mark.django_db
def test_wiadomosc_z_pasujacym_url_zostaje_oznaczona(admin_user, request_na_url):
    """Semantyka zachowana: wiadomość cytująca URL zostaje przeczytana."""
    msg = _utworz_wiadomosc(
        admin_user, "Zobacz /lista/publikacji/ aby sprawdzić wynik."
    )

    _przetworz(request_na_url(admin_user, "/lista/publikacji/"))

    msg.refresh_from_db()
    assert msg.read is True


@pytest.mark.django_db
def test_wiadomosc_bez_pasujacego_url_zostaje_nieprzeczytana(
    admin_user, request_na_url
):
    """Wiadomość niecytująca odwiedzanego URL-a pozostaje nieprzeczytana."""
    msg = _utworz_wiadomosc(
        admin_user, "Zobacz /zupelnie/inny/adres/ aby sprawdzić wynik."
    )

    _przetworz(request_na_url(admin_user, "/lista/publikacji/"))

    msg.refresh_from_db()
    assert msg.read is False


@pytest.mark.django_db
def test_wiadomosc_innego_uzytkownika_nie_jest_ruszana(
    admin_user, django_user_model, request_na_url
):
    """Wiadomość cudza nie zostaje oznaczona, mimo pasującego URL-a."""
    obcy = django_user_model.objects.create_user(
        username="obcy", password="x"  # nosec B106
    )
    msg = _utworz_wiadomosc(
        obcy, "Zobacz /lista/publikacji/ aby sprawdzić wynik."
    )

    _przetworz(request_na_url(admin_user, "/lista/publikacji/"))

    msg.refresh_from_db()
    assert msg.read is False

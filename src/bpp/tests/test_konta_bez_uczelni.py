import logging
from unittest import mock

import pytest
from django.contrib.auth.signals import user_logged_in
from django.contrib.messages import get_messages
from django.contrib.messages.storage.cookie import CookieStorage
from django.db import DatabaseError
from django.test import RequestFactory
from django.utils.safestring import SafeData
from model_bakery import baker

from bpp.konta_bez_uczelni import (
    konta_staff_bez_uczelni,
    url_listy_kont_bez_uczelni,
)
from bpp.models import BppUser

HASLO = "poprawne-haslo-testowe-123"
LINK = '<a href="/admin/bpp/bppuser/?dostep_do_uczelni=brak">'


def _zaloguj(client, username, next_url="/admin/bpp/bppuser/"):
    return client.post(
        "/admin/login/",
        {"username": username, "password": HASLO, "next": next_url},
        follow=True,
    )


def _superuser(username="szef"):
    return BppUser.objects.create_superuser(
        username=username, password=HASLO, email=f"{username}@example.com"
    )


def _staff(username, **kw):
    return baker.make(BppUser, username=username, is_staff=True, is_active=True, **kw)


def _komunikaty(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


@pytest.mark.django_db
def test_konta_staff_bez_uczelni_regula(uczelnia1):
    przypisany = _staff("k_przypisany")
    przypisany.accessible_uczelnie.add(uczelnia1)
    _staff("k_superadmin", is_superuser=True)
    baker.make(BppUser, username="k_nieaktywny", is_staff=True, is_active=False)
    baker.make(BppUser, username="k_zwykly", is_staff=False, is_active=True)
    _staff("k_bezuczelni")

    assert list(konta_staff_bez_uczelni().values_list("username", flat=True)) == [
        "k_bezuczelni"
    ]


@pytest.mark.django_db
def test_superuser_po_zalogowaniu_dostaje_komunikat_z_linkiem(
    client, uczelnia1, uczelnia2
):
    _superuser()
    _staff("staff1")
    _staff("staff2")

    response = _zaloguj(client, "szef")

    assert response.status_code == 200
    tresc = response.content.decode()
    # Link renderuje się jako element <a> (nie jako escapowany tekst).
    assert LINK in tresc
    assert "&lt;a href" not in tresc
    assert "wynosi 2." in tresc


@pytest.mark.django_db
def test_komunikat_przechodzi_przez_storage_jako_safestring(
    client, uczelnia1, uczelnia2
):
    _superuser()
    _staff("staff1")

    # Bez follow: komunikat zostaje zapisany w storage (cookie) i jest
    # odczytywany przy kolejnym żądaniu — po deserializacji ma być SafeData.
    client.post("/admin/login/", {"username": "szef", "password": HASLO})
    request = RequestFactory().get("/")
    request.COOKIES[CookieStorage.cookie_name] = client.cookies[
        CookieStorage.cookie_name
    ].value

    # Filtr po treści: inne handlery user_logged_in (np. ostrzeżenie
    # bpp.W201 o konfiguracji Microsoft) mogą dodać własne komunikaty.
    wiadomosci = [
        m for m in CookieStorage(request) if "Pokaż te konta" in str(m.message)
    ]

    assert len(wiadomosci) == 1
    assert isinstance(wiadomosci[0].message, SafeData)
    assert LINK in wiadomosci[0].message


@pytest.mark.django_db
def test_front_renderuje_link_jako_html(client, uczelnia1, uczelnia2):
    _superuser()
    _staff("staff1")

    response = _zaloguj(client, "szef", next_url="/")

    tresc = response.content.decode()
    # Szablon frontu przekazuje komunikat przez escapejs do pola ``html``:
    # SafeString -> ``\u003Ca href=...``; escapowany tekst dałby ``&lt;a``.
    assert "\\u003Ca href\\u003D\\u0022/admin/bpp/bppuser/" in tresc
    assert "&amp;lt;a href" not in tresc


@pytest.mark.django_db
def test_zwykly_staff_nie_dostaje_komunikatu(client, uczelnia1, uczelnia2):
    u = _staff("staff1")
    u.set_password(HASLO)
    u.save()
    _staff("staff2")

    response = _zaloguj(client, "staff1", next_url="/admin/")

    assert not any("Pokaż te konta" in m for m in _komunikaty(response))
    assert "dostep_do_uczelni=brak" not in response.content.decode()


@pytest.mark.django_db
def test_jedna_uczelnia_brak_komunikatu(client, uczelnia1):
    _superuser()
    _staff("staff1")

    response = _zaloguj(client, "szef")

    assert LINK not in response.content.decode()


@pytest.mark.django_db
def test_brak_takich_kont_brak_komunikatu(client, uczelnia1, uczelnia2):
    _superuser()
    _staff("staff1").accessible_uczelnie.add(uczelnia1)

    response = _zaloguj(client, "szef")

    assert LINK not in response.content.decode()


@pytest.mark.django_db
def test_blad_bazy_nie_blokuje_logowania(client, uczelnia1, uczelnia2, caplog):
    _superuser()
    _staff("staff1")

    with (
        mock.patch(
            "bpp.konta_bez_uczelni.jest_wiele_uczelni",
            side_effect=DatabaseError("brak tabeli"),
        ),
        caplog.at_level(logging.WARNING, logger="bpp.konta_bez_uczelni"),
    ):
        response = _zaloguj(client, "szef")

    assert response.status_code == 200
    assert "_auth_user_id" in client.session
    assert LINK not in response.content.decode()
    assert "Nie udało się sprawdzić" in caplog.text


@pytest.mark.django_db
def test_nieoczekiwany_blad_nie_blokuje_logowania(client, uczelnia1, uczelnia2, caplog):
    _superuser()

    with mock.patch(
        "bpp.konta_bez_uczelni.konta_staff_bez_uczelni",
        side_effect=RuntimeError("cos"),
    ):
        response = _zaloguj(client, "szef")

    assert response.status_code == 200
    assert "_auth_user_id" in client.session
    assert "Nieoczekiwany błąd" in caplog.text


def test_handler_podpiety_pod_user_logged_in():
    klucze = [klucz for klucz, *_ in user_logged_in.receivers]
    assert any(k[0] == "bpp.ostrzez_superusera_po_zalogowaniu" for k in klucze)


@pytest.mark.django_db
def test_filtr_admina_zwraca_wlasciwe_konta(admin_client, uczelnia1, uczelnia2):
    przypisany = _staff("k_przypisany")
    przypisany.accessible_uczelnie.add(uczelnia1)
    baker.make(BppUser, username="k_nieaktywny", is_staff=True, is_active=False)
    baker.make(BppUser, username="k_zwykly", is_staff=False, is_active=True)
    _staff("k_bezuczelni")

    response = admin_client.get(url_listy_kont_bez_uczelni())

    assert response.status_code == 200
    wynik = {u.username for u in response.context["cl"].result_list}
    assert wynik == {"k_bezuczelni"}

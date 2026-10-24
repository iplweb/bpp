"""Ustawienie ``Uczelnia.pokazuj_ranking_autorow`` egzekwowane po stronie
serwera — dla formularza, wyników i eksportu (nie tylko w menu)."""

import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from django.shortcuts import resolve_url
from django.urls import reverse

from bpp.const import GR_RAPORTY_WYSWIETLANIE
from bpp.models import OpcjaWyswietlaniaField

ZAWSZE = OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
ZALOGOWANYM = OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM
ZESPOL = OpcjaWyswietlaniaField.POKAZUJ_GDY_W_ZESPOLE
NIGDY = OpcjaWyswietlaniaField.POKAZUJ_NIGDY

LOGIN = "login"  # oczekiwane: 302 na stronę logowania


def _urle():
    wyniki = reverse("bpp:ranking-autorow", args=(2000, 2030))
    return {
        "formularz": reverse("bpp:ranking_autorow_formularz"),
        "wyniki": wyniki,
        "eksport": wyniki + "?_export=xlsx",
    }


# (ustawienie, rola) -> oczekiwany status
OCZEKIWANE = {
    (ZAWSZE, "anonim"): 200,
    (ZAWSZE, "uzytkownik"): 200,
    (ZAWSZE, "w_grupie"): 200,
    (ZAWSZE, "superuser"): 200,
    (ZALOGOWANYM, "anonim"): LOGIN,
    (ZALOGOWANYM, "uzytkownik"): 403,
    (ZALOGOWANYM, "w_grupie"): 200,
    (ZALOGOWANYM, "superuser"): 200,
    (ZESPOL, "anonim"): LOGIN,
    (ZESPOL, "uzytkownik"): 403,
    (ZESPOL, "w_grupie"): 403,
    (ZESPOL, "superuser"): 200,
    (NIGDY, "anonim"): 404,
    (NIGDY, "uzytkownik"): 404,
    (NIGDY, "w_grupie"): 404,
    (NIGDY, "superuser"): 404,
}


@pytest.fixture
def klient_dla_roli(client, django_user_model):
    def _klient(rola):
        if rola == "anonim":
            return client
        if rola == "superuser":
            user = django_user_model.objects.create_superuser(
                username="su", password="x", email="su@example.com"
            )
        else:
            user = django_user_model.objects.create_user(username=rola, password="x")
            if rola == "w_grupie":
                grupa, _ = Group.objects.get_or_create(name=GR_RAPORTY_WYSWIETLANIE)
                user.groups.add(grupa)
        client.force_login(user)
        return client

    return _klient


@pytest.mark.django_db
@pytest.mark.parametrize("widok", ["formularz", "wyniki", "eksport"])
@pytest.mark.parametrize(("ustawienie", "rola"), list(OCZEKIWANE))
def test_ranking_autorow_respektuje_pokazuj_ranking_autorow(
    uczelnia, klient_dla_roli, widok, ustawienie, rola
):
    uczelnia.pokazuj_ranking_autorow = ustawienie
    uczelnia.save()

    url = _urle()[widok]
    res = klient_dla_roli(rola).get(url)

    oczekiwane = OCZEKIWANE[(ustawienie, rola)]
    if oczekiwane == LOGIN:
        assert res.status_code == 302
        assert res["Location"].startswith(resolve_url(settings.LOGIN_URL))
    else:
        assert res.status_code == oczekiwane

    if widok == "eksport" and oczekiwane == 200:
        assert "attachment" in res.get("Content-Disposition", "")

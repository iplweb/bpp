"""Eksport prac autora (BibTeX/RIS) stosuje te same reguły widoczności,
co publiczna strona autora i strony rekordów:

- autor z ``pokazuj=False`` — 404 dla wszystkich poza redaktorem
  (``moze_wprowadzac_dane``), jak w ``AutorView`` (wspólny helper
  ``wyklucz_ukrytych_autorow``);
- prace o statusach korekty ukrytych w kanale ``podglad`` nie trafiają do
  pliku z zadania w tle (zawsze zakres publiczny, niezależnie od
  zlecającego);
- profil autora przy nieustalonej uczelni wyklucza statusy ukryte
  w kanale ``podglad`` w dowolnej uczelni (fail-closed).
"""

import pytest
from django.contrib.auth.models import AnonymousUser, Group
from django.test import RequestFactory
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import (
    Autor,
    AutorEksportTask,
    Rekord,
    Status_Korekty,
    Uczelnia,
    Ukryj_Status_Korekty,
    Wydawnictwo_Ciagle,
)
from bpp.profil_autora_dane import ukryte_statusy_podgladu

TOKEN_UKRYTY = "kwazarniewidzialny"
TOKEN_JAWNY = "pulsarwidoczny"

ROLE = ["anonim", "zwykly", "redaktor"]


def _uzytkownik(django_user_model, rola):
    user = django_user_model.objects.create_user(rola)
    if rola == "redaktor":
        grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
        user.groups.add(grupa)
    return user


def _zaloguj(client, django_user_model, rola):
    if rola == "anonim":
        return
    client.force_login(_uzytkownik(django_user_model, rola))


@pytest.fixture
def delay(mocker):
    return mocker.patch("bpp.tasks.generuj_eksport_autora.delay")


@pytest.fixture
def autor_ukryty(uczelnia):
    return baker.make(Autor, imiona="Ukryty", nazwisko="Autorukryty", pokazuj=False)


@pytest.fixture
def autor_z_ukryta_praca(
    uczelnia,
    przed_korekta,
    po_korekcie,
    autor_jan_kowalski,
    jednostka,
    typ_odpowiedzialnosci_autor,
):
    for tytul, status in (
        (f"Tajny {TOKEN_UKRYTY} artykul", przed_korekta),
        (f"Jawny {TOKEN_JAWNY} artykul", po_korekcie),
    ):
        pub = baker.make(
            Wydawnictwo_Ciagle,
            tytul_oryginalny=tytul,
            rok=2031,
            status_korekty=status,
        )
        pub.dodaj_autora(autor_jan_kowalski, jednostka, zapisany_jako="Kowalski Jan")
    Rekord.objects.full_refresh()
    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)
    return autor_jan_kowalski


# --- ukryty autor: eksport synchroniczny ----------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("nazwa", ["autor_eksport_bibtex", "autor_eksport_ris"])
@pytest.mark.parametrize(
    "rola,oczekiwany", [("anonim", 302), ("zwykly", 404), ("redaktor", 200)]
)
def test_eksport_sync_ukryty_autor(
    client, django_user_model, autor_ukryty, nazwa, rola, oczekiwany
):
    # Anonim dostaje przekierowanie do logowania (LoginRequiredMixin) zanim
    # w ogóle dojdzie do autora.
    _zaloguj(client, django_user_model, rola)
    res = client.get(reverse(f"bpp:{nazwa}", args=(autor_ukryty.pk,)))
    assert res.status_code == oczekiwany


# --- ukryty autor: start eksportu asynchronicznego ------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("rola", ROLE)
def test_start_eksportu_get_ukryty_autor(
    client, django_user_model, autor_ukryty, delay, rola
):
    _zaloguj(client, django_user_model, rola)
    url = reverse("bpp:autor_eksport_start", args=(autor_ukryty.pk, "bib"))
    res = client.get(url)
    assert res.status_code == (200 if rola == "redaktor" else 404)


@pytest.mark.django_db
@pytest.mark.parametrize("rola", ["anonim", "zwykly"])
def test_start_eksportu_post_ukryty_autor_404(
    client, django_user_model, autor_ukryty, delay, rola
):
    _zaloguj(client, django_user_model, rola)
    url = reverse("bpp:autor_eksport_start", args=(autor_ukryty.pk, "bib"))
    res = client.post(url)
    assert res.status_code == 404
    assert not AutorEksportTask.objects.exists()
    delay.assert_not_called()


@pytest.mark.django_db
def test_start_eksportu_post_ukryty_autor_redaktor(
    client, django_user_model, autor_ukryty, delay
):
    _zaloguj(client, django_user_model, "redaktor")
    url = reverse("bpp:autor_eksport_start", args=(autor_ukryty.pk, "bib"))
    res = client.post(url)
    assert res.status_code == 302
    delay.assert_called_once()


# --- ukryte statusy: eksport w tle ---------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("rola", ROLE)
def test_start_eksportu_zawsze_zakres_publiczny(
    client, django_user_model, autor_z_ukryta_praca, uczelnia, przed_korekta, rola
):
    """Plik z zadania jest publiczny po UUID — zakres nie zależy od tego,
    kto zlecił eksport (także redaktor dostaje plik bez ukrytych prac)."""
    from unittest import mock

    from bpp.tasks import generuj_eksport_autora

    _zaloguj(client, django_user_model, rola)
    url = reverse("bpp:autor_eksport_start", args=(autor_z_ukryta_praca.pk, "bib"))
    with (
        mock.patch("bpp.tasks.generuj_eksport_autora.delay") as delay,
        mock.patch("django_altcha.altcha.verify_solution", return_value=(True, None)),
    ):
        res = client.post(url, {"captcha": "eyJjaGFsbGVuZ2UiOiAieCJ9"})
    assert res.status_code == 302

    task = AutorEksportTask.objects.get()
    assert task.ukryte_statusy == [przed_korekta.pk]
    delay.assert_called_once_with(str(task.pk))

    generuj_eksport_autora(str(task.pk))
    task.refresh_from_db()
    body = task.result_file.read().decode("utf-8")
    assert TOKEN_JAWNY in body
    assert TOKEN_UKRYTY not in body


# --- ukryte_statusy_podgladu: fail-closed bez uczelni ---------------------


def _ukryj(uczelnia, status, **kanaly):
    wszystkie = dict(
        multiwyszukiwarka=False,
        podglad=False,
        raporty=False,
        rankingi=False,
        sloty=False,
        api=False,
        cerif=False,
    )
    wszystkie.update(kanaly)
    return Ukryj_Status_Korekty.objects.create(
        uczelnia=uczelnia, status_korekty=status, **wszystkie
    )


def _request(user=None):
    req = RequestFactory().get("/")
    req.user = user or AnonymousUser()
    return req


@pytest.fixture
def dwie_uczelnie_rozne_statusy(uczelnia):
    inna = baker.make(Uczelnia, skrot="IN", nazwa="Inna uczelnia")
    s1, s2, s3 = (baker.make(Status_Korekty, nazwa=f"st-{i}") for i in range(3))
    _ukryj(uczelnia, s1, podglad=True)
    _ukryj(inna, s2, podglad=True)
    _ukryj(inna, s1, podglad=True)
    # Ukryty tylko w innym kanale — nie dotyczy podglądu.
    _ukryj(inna, s3, api=True, raporty=True)
    return uczelnia, inna, (s1, s2, s3)


@pytest.mark.django_db
def test_ukryte_statusy_podgladu_bez_uczelni_suma_wszystkich(
    dwie_uczelnie_rozne_statusy, mocker
):
    _, _, (s1, s2, _s3) = dwie_uczelnie_rozne_statusy
    mocker.patch("bpp.profil_autora_dane._uczelnia", return_value=None)
    assert ukryte_statusy_podgladu(_request()) == sorted([s1.pk, s2.pk])


@pytest.mark.django_db
def test_ukryte_statusy_podgladu_bez_uczelni_redaktor_widzi_wszystko(
    dwie_uczelnie_rozne_statusy, mocker, django_user_model
):
    mocker.patch("bpp.profil_autora_dane._uczelnia", return_value=None)
    redaktor = _uzytkownik(django_user_model, "redaktor")
    assert ukryte_statusy_podgladu(_request(redaktor)) == []


@pytest.mark.django_db
def test_ukryte_statusy_podgladu_z_uczelnia_tylko_jej_statusy(
    dwie_uczelnie_rozne_statusy,
):
    uczelnia, _inna, (s1, _s2, _s3) = dwie_uczelnie_rozne_statusy
    req = _request()
    assert ukryte_statusy_podgladu(req, uczelnia=uczelnia) == [s1.pk]

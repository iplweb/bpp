"""Metryki wydziałów i podgląd zestawień jako strona serwisu (FD#617)."""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Dyscyplina_Naukowa, Jednostka, Uczelnia
from ewaluacja_metryki import metryki_jednostek as r
from ewaluacja_metryki.metryki_jednostek import (
    zbuduj_metryki_jednostki,
    zbuduj_metryki_wydzialu,
)

from .conftest import wybierz_okres
from .test_metryki_jednostek import _metryka, _uzytkownik


@pytest.fixture
def wydzial(db, okres_2022):
    """Wydział (korzeń drzewa) z dwiema klinikami i jedną osobą przypisaną
    wprost do wydziału; obok drugi wydział, który nie może się wmieszać."""
    uczelnia = baker.make(Uczelnia, uzywaj_wydzialow=True)
    wydzial = baker.make(Jednostka, nazwa="Wydział Testowy", uczelnia=uczelnia)
    klinika_a = baker.make(
        Jednostka, nazwa="Klinika A", uczelnia=uczelnia, parent=wydzial
    )
    klinika_b = baker.make(
        Jednostka, nazwa="Klinika B", uczelnia=uczelnia, parent=wydzial
    )
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="nauki medyczne", kod="3.2")
    _metryka(klinika_a, dyscyplina, okres_2022, "Alfa", 4, 4, 400)
    _metryka(klinika_a, dyscyplina, okres_2022, "Beta", 4, 1, 20)
    _metryka(klinika_b, dyscyplina, okres_2022, "Gamma", 4, 2, 200)
    _metryka(wydzial, dyscyplina, okres_2022, "Dziekanowa", 4, 4, 300)

    inny = baker.make(Jednostka, nazwa="Inny Wydział", uczelnia=uczelnia)
    _metryka(inny, dyscyplina, okres_2022, "Obca", 4, 4, 800)
    return wydzial, klinika_a, klinika_b


def _url(wydzial, **kwargs):
    return reverse("ewaluacja_metryki:metryki_wydzialu", args=[wydzial.pk])


@pytest.mark.django_db
def test_zestawienie_wydzialu_obejmuje_cale_drzewo(wydzial, okres_2022):
    korzen, klinika_a, klinika_b = wydzial
    raport = zbuduj_metryki_wydzialu(korzen, korzen.uczelnia, okres_2022)

    assert raport.wydzial
    (grupa,) = raport.grupy
    assert {w.autor.nazwisko for w in grupa.wiersze} == {
        "Alfa",
        "Beta",
        "Gamma",
        "Dziekanowa",
    }
    # podsumowanie jednostek: od największej liczby punktów
    assert [p.jednostka for p in raport.jednostki] == [klinika_a, korzen, klinika_b]
    klinika = raport.jednostki[0]
    assert klinika.liczba_autorow == 2
    assert klinika.punkty == 420
    assert klinika.wypelnienie == 5 * 100 / 8


@pytest.mark.django_db
def test_zestawienie_wydzialu_mowi_o_wydziale(wydzial, okres_2022):
    korzen, klinika_a, _ = wydzial
    (grupa,) = zbuduj_metryki_wydzialu(korzen, korzen.uczelnia, okres_2022).grupy
    filar = next(w for w in grupa.wiersze if w.kwadrant == r.KWADRANT_FILAR)
    assert filar.opis_kwadrantu == "Filar wydziału"
    assert any(w.startswith("Wydział wypełnia") for w in grupa.wnioski)
    assert any("mediany wydziału" in z for _, z, _ in grupa.zalecenia_wg_grup)

    # zestawienie jednostki bez zmian
    (grupa_j,) = zbuduj_metryki_jednostki(
        klinika_a, klinika_a.uczelnia, okres_2022
    ).grupy
    filar_j = next(w for w in grupa_j.wiersze if w.kwadrant == r.KWADRANT_FILAR)
    assert filar_j.opis_kwadrantu == "Filar jednostki"
    assert any(w.startswith("Jednostka wypełnia") for w in grupa_j.wnioski)


@pytest.mark.django_db
def test_wydzial_pdf_i_podglad(client, wydzial, okres_2022):
    korzen, klinika_a, _ = wydzial
    _uzytkownik(client, is_superuser=True, is_staff=True)
    wybierz_okres(client, okres_2022)

    pdf = client.get(_url(korzen))
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert "metryki_wydzialu_" in pdf["Content-Disposition"]

    podglad = client.get(_url(korzen), {"format": "html"})
    assert podglad.status_code == 200
    tresc = podglad.content.decode()
    assert "Metryki ewaluacyjne wydziału" in tresc
    assert "Jednostki wydziału" in tresc
    assert "Obca" not in tresc
    # podgląd to strona serwisu: okruszki do listy wydziałów, przycisk PDF
    assert reverse("ewaluacja_metryki:metryki_wydzialow") in tresc
    assert f'href="{_url(korzen)}"' in tresc
    # jednostki wydziału prowadzą do swoich podglądów
    url_kliniki = reverse("ewaluacja_metryki:metryki_jednostki", args=[klinika_a.pk])
    assert f"{url_kliniki}?format=html" in tresc


@pytest.mark.django_db
def test_podglad_jednostki_to_strona_serwisu(client, wydzial, okres_2022):
    _, klinika_a, _ = wydzial
    _uzytkownik(client, is_superuser=True, is_staff=True)
    wybierz_okres(client, okres_2022)
    url = reverse("ewaluacja_metryki:metryki_jednostki", args=[klinika_a.pk])

    tresc = client.get(url, {"format": "html"}).content.decode()
    assert 'class="current">Klinika A<' in tresc
    assert reverse("ewaluacja_metryki:metryki_jednostek") in tresc
    assert "Pobierz PDF" in tresc
    assert "file://" not in tresc  # fonty z adresu statyków, nie z dysku


@pytest.mark.django_db
def test_wydzial_to_tylko_korzen_drzewa(client, wydzial, okres_2022):
    _, klinika_a, _ = wydzial
    _uzytkownik(client, is_superuser=True, is_staff=True)
    wybierz_okres(client, okres_2022)
    assert client.get(_url(klinika_a)).status_code == 404


@pytest.mark.django_db
def test_bez_wydzialow_brak_metryk_wydzialow(client, wydzial, okres_2022):
    korzen, _, _ = wydzial
    Uczelnia.objects.update(uzywaj_wydzialow=False)
    _uzytkownik(client, is_superuser=True, is_staff=True)
    wybierz_okres(client, okres_2022)
    assert client.get(reverse("ewaluacja_metryki:metryki_wydzialow")).status_code == 404
    assert client.get(_url(korzen)).status_code == 404
    lista = client.get(reverse("ewaluacja_metryki:metryki_jednostek"))
    assert reverse("ewaluacja_metryki:metryki_wydzialow") not in lista.content.decode()


@pytest.mark.django_db
def test_lista_wydzialow(client, wydzial, okres_2022):
    korzen, _, _ = wydzial
    _uzytkownik(client, is_superuser=True, is_staff=True)
    wybierz_okres(client, okres_2022)
    tresc = client.get(reverse("ewaluacja_metryki:metryki_wydzialow")).content.decode()
    assert "Wydział Testowy" in tresc
    assert "Inny Wydział" in tresc
    assert _url(korzen) in tresc


@pytest.mark.django_db
def test_wglad_w_wydzial_tylko_z_wgladem_w_korzen(client, wydzial, okres_2022):
    korzen, klinika_a, _ = wydzial
    user = _uzytkownik(client)
    wybierz_okres(client, okres_2022)

    # wgląd w jedną klinikę nie daje wglądu w cały wydział
    user.jednostki_metryk.add(klinika_a)
    assert client.get(_url(korzen), {"format": "html"}).status_code == 403
    lista = client.get(reverse("ewaluacja_metryki:metryki_wydzialow"))
    assert "Wydział Testowy" not in lista.content.decode()

    # wgląd w wydział (korzeń) — tak, ale tylko w ten wydział
    user.jednostki_metryk.add(korzen)
    assert client.get(_url(korzen), {"format": "html"}).status_code == 200
    tresc = client.get(reverse("ewaluacja_metryki:metryki_wydzialow")).content.decode()
    assert "Wydział Testowy" in tresc
    assert "Inny Wydział" not in tresc

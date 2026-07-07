"""Testy bezpiecznego kasowania jednostek (spec 2026-07-07).

Logika modelu: ``Jednostka.przeszkody_w_kasowaniu`` /
``Jednostka.czy_mozna_skasowac`` — jednostkę można skasować wyłącznie gdy
ma ZERO odwrotnych referencji z realnych, zarządzanych tabel (podjednostki,
Autor_Jednostka, własna historia Jednostka_Rodzic, ...). Niezarządzane widoki
SQL i relacje generyczne NIE blokują.
"""

import pytest
from model_bakery import baker

from bpp.models import Autor, Jednostka


@pytest.mark.django_db
def test_przeszkody_w_kasowaniu_pusta_jednostka(jednostka: Jednostka):
    assert jednostka.przeszkody_w_kasowaniu() == []
    assert jednostka.czy_mozna_skasowac() is True


@pytest.mark.django_db
def test_przeszkody_w_kasowaniu_z_autorem(jednostka: Jednostka):
    autor = baker.make(Autor)
    jednostka.dodaj_autora(autor)

    przeszkody = jednostka.przeszkody_w_kasowaniu()

    assert przeszkody != []
    assert jednostka.czy_mozna_skasowac() is False
    # Dodanie autora tworzy DWIE realne referencje: samo powiązanie
    # Autor_Jednostka ORAZ (przez trigger) denorm ``Autor.aktualna_jednostka``.
    # Obie liczą się jako przeszkoda — potwierdza to semantykę „ściśle zero".
    etykiety = {etykieta for etykieta, _ in przeszkody}
    assert any("autor-jednostka" in e for e in etykiety)


@pytest.mark.django_db
def test_przeszkody_w_kasowaniu_z_podjednostka(
    jednostka: Jednostka, jednostka_podrzedna: Jednostka
):
    przeszkody = jednostka.przeszkody_w_kasowaniu()

    assert jednostka.czy_mozna_skasowac() is False
    # Podjednostka pojawia się jako odwrotna relacja self-FK ``parent``.
    assert any("jednostk" in etykieta.lower() for etykieta, _ in przeszkody)


@pytest.mark.django_db
def test_przeszkody_w_kasowaniu_z_wlasna_historia(jednostka: Jednostka):
    # Ściśle zero: własna historia (Jednostka_Rodzic) też blokuje.
    jednostka.jednostka_rodzic_set.create(parent=None)

    assert jednostka.czy_mozna_skasowac() is False


@pytest.mark.django_db
def test_przeszkody_w_kasowaniu_nie_rzuca_na_odwrotnym_o2o(jednostka: Jednostka):
    # Regresja: Jednostka ma odwrotny O2O do niezarządzanego widoku
    # (Nowe_Sumy_View). Liczenie przez akcesor rzuciłoby DoesNotExist —
    # metoda musi liczyć przez pole i pomijać widoki. Pusta jednostka bez
    # publikacji nie ma wiersza w widoku, więc pozostaje kasowalna.
    assert jednostka.czy_mozna_skasowac() is True

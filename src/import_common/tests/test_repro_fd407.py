"""Repro FD#407 — matching autora po polu ``poprzednie_nazwiska``.

Autorka zmieniła nazwisko z dwuczłonowego "Gawlik-Dziki" na jednoczłonowe
"Gawlik" (albo odwrotnie). Rekord w BPP ma nazwisko w jednej z tych form, a
druga forma siedzi w polu ``poprzednie_nazwiska`` (CSV). Importer powinien
dopasować przychodzące nazwisko także po poprzednich nazwiskach — jako
dokładny człon listy (nie podłańcuch), żeby nie generować fałszywych
dopasowań dla częstych nazwisk.
"""

import pytest
from model_bakery import baker

from bpp.models import Autor
from import_common.core import matchuj_autora


@pytest.mark.django_db
def test_matchuje_przychodzace_stare_nazwisko_po_poprzednim():
    """Rekord: nazwisko="Gawlik" + poprzednie="Gawlik-Dziki".

    Przychodzi stara forma "Gawlik-Dziki" (np. z publikacji sprzed zmiany).
    """
    autor = baker.make(
        Autor,
        imiona="Urszula",
        nazwisko="Gawlik",
        poprzednie_nazwiska="Gawlik-Dziki",
    )
    assert matchuj_autora("Urszula", "Gawlik-Dziki") == autor


@pytest.mark.django_db
def test_matchuje_przychodzace_nowe_nazwisko_po_poprzednim():
    """Rekord: nazwisko="Gawlik-Dziki" + poprzednie="Gawlik".

    Przychodzi nowa, jednoczłonowa forma "Gawlik" (dokładnie case ze
    zgłoszenia: BPBP przysyła GAWLIK, w bazie Gawlik-Dziki).
    """
    autor = baker.make(
        Autor,
        imiona="Urszula",
        nazwisko="Gawlik-Dziki",
        poprzednie_nazwiska="Gawlik",
    )
    assert matchuj_autora("Urszula", "Gawlik") == autor


@pytest.mark.django_db
def test_matchuje_po_jednym_z_wielu_poprzednich_nazwisk():
    """Pole to lista CSV — każdy człon powinien dać dopasowanie."""
    autor = baker.make(
        Autor,
        imiona="Anna",
        nazwisko="Nowak",
        poprzednie_nazwiska="Kowalska, Gawlik-Dziki",
    )
    assert matchuj_autora("Anna", "Kowalska") == autor
    assert matchuj_autora("Anna", "Gawlik-Dziki") == autor


@pytest.mark.django_db
def test_nie_matchuje_fragmentu_poprzedniego_nazwiska():
    """Dokładny człon, nie podłańcuch: "Gawlik" NIE trafia w "Nowak-Gawlikowska".

    To gwarancja bezpieczeństwa ze zgłoszenia — częste nazwiska nie mogą
    generować fałszywych dopasowań przez zawieranie się w innym nazwisku.
    """
    baker.make(
        Autor,
        imiona="Anna",
        nazwisko="Nowak",
        poprzednie_nazwiska="Nowak-Gawlikowska",
    )
    assert matchuj_autora("Anna", "Gawlik") is None


@pytest.mark.django_db
def test_matchuje_poprzednie_nazwisko_z_wariantem_polsko_angielskim():
    """Fallback PL↔EN uwzględnia też poprzednie nazwiska (unaccent).

    Rekord: nazwisko="Kowalski", poprzednie="Marańda", imiona="Ewa".
    Przychodzi "Eva Maranda" (angielska pisownia imienia + nazwisko bez
    diakrytyków). Match tylko przez fold poprzedniego nazwiska.
    """
    autor = baker.make(
        Autor,
        imiona="Ewa",
        nazwisko="Kowalski",
        poprzednie_nazwiska="Marańda",
    )
    assert matchuj_autora("Eva", "Maranda") == autor

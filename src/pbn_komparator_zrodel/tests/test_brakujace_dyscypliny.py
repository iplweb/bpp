"""Testy skanu brakujących dyscyplin PBN.

Pokrywają ``znajdz_brakujace_dyscypliny_pbn`` i
``aktualizuj_brakujace_dyscypliny_pbn`` — funkcje wołane na końcu
``download_journals`` (krok „Aktualizacja brakujących dyscyplin...", 90%).
Pinują poprawność zanim zmienimy iterację po ``Journal`` na strumieniową
(``.iterator()``) i zdedupujemy obie funkcje do jednego źródła prawdy.
"""

import pytest
from model_bakery import baker

from bpp.models import Dyscyplina_Naukowa
from pbn_api.models import Journal

from ..models import BrakujacaDyscyplinaPBN
from ..utils import (
    aktualizuj_brakujace_dyscypliny_pbn,
    znajdz_brakujace_dyscypliny_pbn,
)


def _journal(mongo_id, disciplines, current=True):
    """Minimalny Journal PBN z listą dyscyplin w bieżącej wersji."""
    return Journal.objects.create(
        mongoId=mongo_id,
        versions=[{"current": current, "object": {"disciplines": disciplines}}],
    )


@pytest.mark.django_db
def test_znajdz_wykrywa_dyscypliny_nieobecne_w_bpp():
    # W BPP istnieje tylko 1.1; źródło PBN deklaruje 1.1 (kod 11) oraz 2.3 (kod 23).
    baker.make(Dyscyplina_Naukowa, kod="1.1", nazwa="Matematyka")
    _journal(
        "j1",
        [
            {"code": "11", "name": "Matematyka"},
            {"code": "23", "name": "Nauki chemiczne"},
        ],
    )

    brakujace = znajdz_brakujace_dyscypliny_pbn()

    assert set(brakujace) == {"23"}
    assert brakujace["23"]["kod_bpp"] == "2.3"
    assert brakujace["23"]["nazwa"] == "Nauki chemiczne"
    assert brakujace["23"]["count"] == 1


@pytest.mark.django_db
def test_znajdz_zlicza_wystapienia_w_wielu_zrodlach():
    baker.make(Dyscyplina_Naukowa, kod="1.1")
    _journal("j1", [{"code": "23", "name": "Chem"}])
    _journal("j2", [{"code": "23", "name": "Chem"}])

    brakujace = znajdz_brakujace_dyscypliny_pbn()

    assert brakujace["23"]["count"] == 2


@pytest.mark.django_db
def test_znajdz_pomija_zrodla_bez_current_version_i_bez_dyscyplin():
    baker.make(Dyscyplina_Naukowa, kod="1.1")
    # brak wersji oznaczonej current -> value(..., return_none=True) zwraca None
    Journal.objects.create(mongoId="nocur", versions=[{"current": False, "object": {}}])
    # obecna wersja, ale pusta lista dyscyplin
    _journal("empty", [])

    assert znajdz_brakujace_dyscypliny_pbn() == {}


@pytest.mark.django_db
def test_aktualizuj_zapisuje_do_bazy_i_zastepuje_stare():
    baker.make(Dyscyplina_Naukowa, kod="1.1")
    # Nieaktualny wpis, który musi zniknąć po ponownym skanie.
    BrakujacaDyscyplinaPBN.objects.create(
        kod_pbn="99", kod_bpp="9.9", nazwa="Stare", liczba_zrodel=5
    )
    _journal("j1", [{"code": "23", "name": "Chem"}])

    ile = aktualizuj_brakujace_dyscypliny_pbn()

    assert ile == 1
    wpisy = {b.kod_pbn: b for b in BrakujacaDyscyplinaPBN.objects.all()}
    assert set(wpisy) == {"23"}  # stary "99" usunięty
    assert wpisy["23"].kod_bpp == "2.3"
    assert wpisy["23"].nazwa == "Chem"
    assert wpisy["23"].liczba_zrodel == 1


@pytest.mark.django_db
def test_aktualizuj_zapisuje_dokladnie_to_co_zwraca_znajdz():
    """Jedno źródło prawdy: zapis do bazy == wynik ``znajdz_...``."""
    baker.make(Dyscyplina_Naukowa, kod="1.1")
    _journal(
        "j1",
        [{"code": "23", "name": "Chem"}, {"code": "31", "name": "Bio"}],
    )

    znalezione = znajdz_brakujace_dyscypliny_pbn()
    aktualizuj_brakujace_dyscypliny_pbn()

    zapisane = {
        b.kod_pbn: {"kod_bpp": b.kod_bpp, "nazwa": b.nazwa, "count": b.liczba_zrodel}
        for b in BrakujacaDyscyplinaPBN.objects.all()
    }
    assert zapisane == znalezione

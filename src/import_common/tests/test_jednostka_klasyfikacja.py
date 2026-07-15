"""Testy klasyfikacji jednostki (nie-rzucającej) i generowania skrótu —
fundament tworzenia brakujących jednostek w imporcie pracowników."""

import pytest
from model_bakery import baker

from bpp.models import Jednostka
from import_common.core.jednostka import (
    PROG_ZGADYWANIA_JEDNOSTKI,
    sklasyfikuj_jednostke,
    unikalny_skrot,
    zaproponuj_skrot,
)
from import_pracownikow.pewnosc import STATUS_BRAK, STATUS_TWARDY, STATUS_ZGADYWANIE

# --- zaproponuj_skrot (czysta funkcja, bez DB) ---------------------------------


@pytest.mark.parametrize(
    "nazwa,oczekiwany",
    [
        ("Zakład Transfuzjologii", "ZT"),
        ("Zakład Hematologii Eksperymentalnej", "ZHE"),
        # słowa pisane małą literą (spójniki) pomijane w akronimie
        ("Zakład i Katedra Onkologii", "ZKO"),
        # jeden znaczący wyraz → akronim za krótki → fallback do nazwy
        ("Kardiologia", "Kardiologia"),
    ],
)
def test_zaproponuj_skrot_akronim(nazwa, oczekiwany):
    assert zaproponuj_skrot(nazwa) == oczekiwany


def test_zaproponuj_skrot_fallback_przyciety_do_128():
    nazwa = "A" + "x" * 200  # jeden wyraz, akronim = "A" (za krótki) → fallback
    wynik = zaproponuj_skrot(nazwa)
    assert len(wynik) <= 128
    assert wynik == nazwa[:128]


def test_zaproponuj_skrot_pusty():
    assert zaproponuj_skrot("") == ""
    assert zaproponuj_skrot("   ") == ""


# --- unikalny_skrot (DB + zbiór in-batch) --------------------------------------


@pytest.mark.django_db
def test_unikalny_skrot_bez_kolizji():
    assert unikalny_skrot("ZT") == "ZT"


@pytest.mark.django_db
def test_unikalny_skrot_kolizja_w_bazie():
    baker.make(Jednostka, skrot="ZT")
    assert unikalny_skrot("ZT") == "ZT2"


@pytest.mark.django_db
def test_unikalny_skrot_kolizja_in_batch():
    # "zajete" symuluje skróty utworzone wcześniej w TYM SAMYM runie integracji
    assert unikalny_skrot("ZT", zajete={"ZT"}) == "ZT2"
    assert unikalny_skrot("ZT", zajete={"ZT", "ZT2"}) == "ZT3"


@pytest.mark.django_db
def test_unikalny_skrot_kolizja_baza_i_batch():
    baker.make(Jednostka, skrot="ZT")
    assert unikalny_skrot("ZT", zajete={"ZT2"}) == "ZT3"


# --- sklasyfikuj_jednostke (DB, trigram) ---------------------------------------


@pytest.mark.django_db
def test_sklasyfikuj_dokladne_dopasowanie_twardy(uczelnia):
    j = baker.make(
        Jednostka, nazwa="Zakład Transfuzjologii", skrot="ZT", uczelnia=uczelnia
    )
    jednostka, status, sim = sklasyfikuj_jednostke("Zakład Transfuzjologii")
    assert jednostka == j
    assert status == STATUS_TWARDY
    assert sim is None


@pytest.mark.django_db
def test_sklasyfikuj_brak_dopasowania(uczelnia):
    baker.make(
        Jednostka, nazwa="Instytut Fizyki Jądrowej", skrot="IFJ", uczelnia=uczelnia
    )
    jednostka, status, sim = sklasyfikuj_jednostke("Zakład Transfuzjologii")
    assert jednostka is None
    assert status == STATUS_BRAK
    assert sim is None


@pytest.mark.django_db
def test_sklasyfikuj_podobne_zgadywanie(uczelnia):
    j = baker.make(
        Jednostka, nazwa="Zakład Transfuzjologii", skrot="ZT", uczelnia=uczelnia
    )
    # wariant bez diakrytyków — NIE matchuje iexact/istartswith, ale trigram wysoki
    jednostka, status, sim = sklasyfikuj_jednostke("Zaklad Transfuzjologii")
    assert status == STATUS_ZGADYWANIE
    assert jednostka == j
    assert sim is not None and sim >= PROG_ZGADYWANIA_JEDNOSTKI


@pytest.mark.django_db
def test_sklasyfikuj_pusta_nazwa_nie_rzuca(uczelnia):
    for pusta in ("", "   ", None):
        jednostka, status, sim = sklasyfikuj_jednostke(pusta)
        assert jednostka is None
        assert status == STATUS_BRAK
        assert sim is None


@pytest.mark.django_db
def test_sklasyfikuj_remis_prefiksowy_nie_rzuca(uczelnia):
    # dwie jednostki o wspólnym prefiksie → matchuj_jednostke rzuca
    # MultipleObjectsReturned; klasyfikator ma to złapać, nie wywrócić się.
    baker.make(
        Jednostka, nazwa="Zakład Biologii Molekularnej", skrot="ZBM", uczelnia=uczelnia
    )
    baker.make(
        Jednostka, nazwa="Zakład Biologii Komórki", skrot="ZBK", uczelnia=uczelnia
    )
    jednostka, status, sim = sklasyfikuj_jednostke("Zakład Biologii")
    assert status in (STATUS_ZGADYWANIE, STATUS_BRAK)  # nie rzuca, wybór lub brak


@pytest.mark.django_db
def test_sklasyfikuj_pula_wyklucza_obce_jednostki(uczelnia):
    # jednostka obca (skupia_pracownikow=False) NIE może być auto-dopasowana
    baker.make(
        Jednostka,
        nazwa="Zaklad Transfuzjologii Obcy",
        skrot="ZTO",
        uczelnia=uczelnia,
        skupia_pracownikow=False,
    )
    jednostka, status, sim = sklasyfikuj_jednostke("Zakład Transfuzjologii")
    assert status == STATUS_BRAK
    assert jednostka is None


# --- fallback po skrócie słów (sklasyfikuj_jednostke) ---------------------------


@pytest.mark.django_db
def test_sklasyfikuj_skrocona_nazwa_zgadywanie(uczelnia):
    j = baker.make(
        Jednostka,
        nazwa=(
            "Zakład Pielęgniarstwa Anestezjologicznego i Intensywnej Opieki Medycznej"
        ),
        skrot="Zakł. Piel. Anestezj.",
        uczelnia=uczelnia,
    )
    jednostka, status, sim = sklasyfikuj_jednostke(
        "Zakład Piel. Anestezjol. i Intens. Opieki Medycznej"
    )
    assert jednostka == j
    assert status == STATUS_ZGADYWANIE
    assert sim is not None  # trigram kandydata (poniżej progu, ale nie None)


@pytest.mark.django_db
def test_sklasyfikuj_skrot_agresywny_pelnowymiarowy_zgadywanie(uczelnia):
    # forma agresywniej skrócona (trigram 0.417) — musi wejść do puli (floor 0.25)
    # i wyrównać się 7/7 do nazwy
    j = baker.make(
        Jednostka,
        nazwa=(
            "Zakład Pielęgniarstwa Anestezjologicznego i Intensywnej Opieki Medycznej"
        ),
        skrot="Zakł. Piel. Anestezj.",
        uczelnia=uczelnia,
    )
    jednostka, status, sim = sklasyfikuj_jednostke(
        "Zakł. Pielęg. Anest. i Inten. Opieki Med."
    )
    assert jednostka == j
    assert status == STATUS_ZGADYWANIE


@pytest.mark.django_db
def test_sklasyfikuj_fragment_w_puli_ale_ponizej_pokrycia_brak(uczelnia):
    # finding #3: input DZIELI słowa z nazwą (trigram 0.313 ≥ floor → wchodzi do
    # puli, więc guard SIĘ WYKONUJE), ale pokrycie 2/7 < 0.6 → BRAK.
    # NIE 'Zakład Pielęgniarstwa' (to złapałby matchuj_jednostke istartswith).
    baker.make(
        Jednostka,
        nazwa=(
            "Zakład Pielęgniarstwa Anestezjologicznego i Intensywnej Opieki Medycznej"
        ),
        skrot="Zakł. Piel. Anestezj.",
        uczelnia=uczelnia,
    )
    jednostka, status, sim = sklasyfikuj_jednostke("Pielęgniarstwa Opieki")
    assert jednostka is None
    assert status == STATUS_BRAK

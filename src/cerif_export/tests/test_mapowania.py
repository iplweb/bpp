"""Migracja mapująca słowniki BPP na wartości kontrolowane profilu.

Testy czytające słownik z bazy żądają fixtur ``charaktery_formalne`` /
``jezyki`` JAWNIE, mimo że dane są też w baseline. Bez tego mierzą stan
zostawiony przez poprzedni test w shardzie: obie fixtury kasują słownik
i odtwarzają go z JSON-a, a test ``transaction=True`` taki podmieniony
słownik utrwala. Dokładnie tak padł CI, mimo zieleni lokalnie.
"""

import importlib

import pytest

from bpp.models import (
    Charakter_Formalny,
    Jezyk,
    Rodzaj_Prawa_Patentowego,
    Tryb_OpenAccess_Wydawnictwo_Ciagle,
)
from cerif_export.slowniki import coar, dostep

migracja = importlib.import_module("bpp.migrations.0480_cerif_mapowania_slownikow")
migracja_frg = importlib.import_module("bpp.migrations.0483_cerif_znak_towarowy")

# Mapowania powstają w DWÓCH migracjach: 0480 (główna partia) i 0483
# (`frg`, doszlifowane po recenzji — 0480 była już zastosowana, więc nie
# wolno jej modyfikować). Fixtura musi zgadzać się z sumą obu.
WSZYSTKIE_CHARAKTERY = dict(migracja.CHARAKTERY, frg=migracja_frg.FRAGMENT_BOOK_PART)


def _coar(skrot):
    return Charakter_Formalny.objects.get(skrot=skrot).coar_type


@pytest.mark.django_db
@pytest.mark.parametrize(
    "skrot,oczekiwany",
    [
        ("AC", coar.BAZA + "c_6501"),
        ("KS", coar.BAZA + "c_2f33"),
        ("ROZ", coar.BAZA + "c_3248"),
        ("D", coar.DOCTORAL_THESIS),
        ("H", coar.THESIS),
        ("CZ", coar.JOURNAL),
    ],
)
def test_charaktery_formalne_zmapowane(charaktery_formalne, skrot, oczekiwany):
    assert _coar(skrot) == oczekiwany


@pytest.mark.django_db
def test_zmapowane_wartosci_naleza_do_slownika_coar(charaktery_formalne):
    """Literówka w URI byłaby niewidoczna aż do odrzucenia przez walidator."""
    for obj in Charakter_Formalny.objects.exclude(coar_type=""):
        assert obj.coar_type in coar.TYPY_TEKSTOWE, obj.skrot

    for obj in Rodzaj_Prawa_Patentowego.objects.exclude(coar_type=""):
        assert obj.coar_type in coar.TYPY_PATENTOWE, obj.nazwa


@pytest.mark.django_db
def test_wieloznaczne_charaktery_zostaja_puste(charaktery_formalne):
    """„inne" i „Fragment" mają zostać dla redakcji, nie być zgadnięte."""
    for skrot in ("IN", "BR", "Supl"):
        assert _coar(skrot) == "", skrot


@pytest.mark.django_db
def test_patenty_nie_dostaja_typu_publikacji(charaktery_formalne):
    """PAT/WYN idą jako encja Patent — typ publikacji byłby tu nieprawdą."""
    for skrot in ("PAT", "WYN"):
        assert _coar(skrot) == "", skrot


@pytest.mark.django_db
@pytest.mark.parametrize(
    "skrot,kod", [("ang.", "en"), ("niem.", "de"), ("pol.", "pl"), ("wł.", "it")]
)
def test_jezyki_maja_kod_bcp47(jezyki, skrot, kod):
    assert Jezyk.objects.get(skrot=skrot).kod_bcp47 == kod


@pytest.mark.django_db
def test_jezyki_nieokreslone_zostaja_bez_kodu(jezyki):
    """„brak danych" i „inny" znaczą „nie wiemy" — xml:lang ma nie powstać."""
    for skrot in ("b/d", "in."):
        assert Jezyk.objects.get(skrot=skrot).kod_bcp47 == ""


@pytest.mark.django_db
def test_prawa_patentowe_zmapowane():
    assert (
        Rodzaj_Prawa_Patentowego.objects.get(nazwa="wynalazek").coar_type
        == coar.PATENT_ROOT
    )
    # Porównanie pełnego URI, nie sufiksu — literówka w prefiksie
    # przeszłaby przez `endswith` niezauważona.
    assert (
        Rodzaj_Prawa_Patentowego.objects.get(nazwa="wzór użytkowy").coar_type
        == coar.BAZA + "9DKX-KSAF"
    )


@pytest.mark.django_db
def test_tryby_otwarte_maja_prawo_dostepu():
    otwarty = Tryb_OpenAccess_Wydawnictwo_Ciagle.objects.get(skrot="OPEN_JOURNAL")
    assert otwarty.coar_access_right == dostep.OPEN

    inny = Tryb_OpenAccess_Wydawnictwo_Ciagle.objects.get(skrot="OTHER")
    assert inny.coar_access_right == "", "Inne nie znaczy otwarte"


@pytest.mark.django_db
def test_fixtura_json_zgodna_z_migracja():
    """Strażnik rozjazdu fixtury testowej i migracji danych.

    ``src/fixtures/conftest_system.py`` kasuje cały słownik charakterów
    i odtwarza go z ``charakter_formalny.json``. Gdy JSON nie ma typów COAR
    (albo ma inne niż migracja), test korzystający z tej fixtury dostaje
    słownik niezgodny z produkcją — i wywraca się dopiero na CI, po tym jak
    wcześniejszy test ``transaction=True`` utrwali podmieniony słownik.

    Dokładnie to się wydarzyło; stąd ten test.
    """
    import json
    import pathlib

    sciezka = pathlib.Path(__file__).parents[2] / "bpp/fixtures/charakter_formalny.json"
    fixtura = {
        rek["fields"]["skrot"]: rek["fields"].get("coar_type", "")
        for rek in json.loads(sciezka.read_text())
    }

    for skrot, uri in WSZYSTKIE_CHARAKTERY.items():
        assert fixtura.get(skrot) == uri, (
            f"{skrot}: fixtura ma {fixtura.get(skrot)!r}, migracja {uri!r}"
        )

    # I odwrotnie: fixtura nie może mieć typów, których migracja nie zna.
    for skrot, uri in fixtura.items():
        if uri:
            assert WSZYSTKIE_CHARAKTERY.get(skrot) == uri, skrot

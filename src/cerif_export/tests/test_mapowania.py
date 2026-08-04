"""Migracja mapująca słowniki BPP na wartości kontrolowane profilu.

Testy sprawdzają dane załadowane z baseline'u — czyli to, co realnie
zobaczy wdrożenie, a nie obiekty zbudowane pod tezę.
"""

import pytest

from bpp.models import (
    Charakter_Formalny,
    Jezyk,
    Rodzaj_Prawa_Patentowego,
    Tryb_OpenAccess_Wydawnictwo_Ciagle,
)
from cerif_export.slowniki import coar, dostep


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
def test_charaktery_formalne_zmapowane(skrot, oczekiwany):
    assert _coar(skrot) == oczekiwany


@pytest.mark.django_db
def test_zmapowane_wartosci_naleza_do_slownika_coar():
    """Literówka w URI byłaby niewidoczna aż do odrzucenia przez walidator."""
    for obj in Charakter_Formalny.objects.exclude(coar_type=""):
        assert obj.coar_type in coar.TYPY_TEKSTOWE, obj.skrot

    for obj in Rodzaj_Prawa_Patentowego.objects.exclude(coar_type=""):
        assert obj.coar_type in coar.TYPY_PATENTOWE, obj.nazwa


@pytest.mark.django_db
def test_wieloznaczne_charaktery_zostaja_puste():
    """„inne" i „Fragment" mają zostać dla redakcji, nie być zgadnięte."""
    for skrot in ("IN", "frg", "BR"):
        assert _coar(skrot) == "", skrot


@pytest.mark.django_db
def test_patenty_nie_dostaja_typu_publikacji():
    """PAT/WYN idą jako encja Patent — typ publikacji byłby tu nieprawdą."""
    for skrot in ("PAT", "WYN"):
        assert _coar(skrot) == "", skrot


@pytest.mark.django_db
@pytest.mark.parametrize(
    "skrot,kod", [("ang.", "en"), ("niem.", "de"), ("pol.", "pl"), ("wł.", "it")]
)
def test_jezyki_maja_kod_bcp47(skrot, kod):
    assert Jezyk.objects.get(skrot=skrot).kod_bcp47 == kod


@pytest.mark.django_db
def test_jezyki_nieokreslone_zostaja_bez_kodu():
    """„brak danych" i „inny" znaczą „nie wiemy" — xml:lang ma nie powstać."""
    for skrot in ("b/d", "in."):
        assert Jezyk.objects.get(skrot=skrot).kod_bcp47 == ""


@pytest.mark.django_db
def test_prawa_patentowe_zmapowane():
    assert (
        Rodzaj_Prawa_Patentowego.objects.get(nazwa="wynalazek").coar_type
        == coar.PATENT_ROOT
    )
    assert Rodzaj_Prawa_Patentowego.objects.get(
        nazwa="wzór użytkowy"
    ).coar_type.endswith("9DKX-KSAF")


@pytest.mark.django_db
def test_tryby_otwarte_maja_prawo_dostepu():
    otwarty = Tryb_OpenAccess_Wydawnictwo_Ciagle.objects.get(skrot="OPEN_JOURNAL")
    assert otwarty.coar_access_right == dostep.OPEN

    inny = Tryb_OpenAccess_Wydawnictwo_Ciagle.objects.get(skrot="OTHER")
    assert inny.coar_access_right == "", "Inne nie znaczy otwarte"

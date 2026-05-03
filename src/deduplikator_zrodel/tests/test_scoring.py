"""Charakterystyczne testy dla scoringu podobieństwa źródeł.

Logika scoringu w `ocen_podobienstwo` decyduje, które kandydujące źródła
będą pokazywane jako duplikaty. Wcześniej kompletnie nie była testowana —
patrz ANALYSIS.md #5 (2026-05-02).

Wagi (z `utils.py:105-212` na dzień 2026-05-02):
- ISSN match: +100
- E-ISSN match: +100
- ISSN + E-ISSN: dodatkowy bonus +20
- PBN UID match: +80
- Identyczna nazwa (po normalizacji, case-insensitive): +60
- Trigram nazwy > 0.9: +40 / > 0.7: +20  (wymaga DB)
- Trigram skrótu > 0.7: +10               (wymaga DB)
- Inny rodzaj_id (oba ustawione): -15
- Inny zasieg_id (oba ustawione): -10

Uwaga: `baker.make(Zrodlo)` auto-uzupełnia FK rodzaj/zasieg losowymi
wartościami, więc każda para zrobiona przez `any_zrodlo()` ma DOMYŚLNIE
różne rodzaj_id+zasieg_id i dostaje karę -25. Żeby testować dokładną
wartość bazowych dopasowań, parujemy zrodla używając wspólnego
rodzaju i zasięgu — fixtury `pair_zrodel` poniżej.
"""

import pytest
from model_bakery import baker

from bpp.models.zrodlo import Rodzaj_Zrodla, Zasieg_Zrodla, Zrodlo
from deduplikator_zrodel.utils import ocen_podobienstwo


@pytest.fixture
def rodzaj():
    return Rodzaj_Zrodla.objects.create(nazwa="Czasopismo")


@pytest.fixture
def zasieg():
    return Zasieg_Zrodla.objects.create(nazwa="Krajowy")


def _make_zrodlo(rodzaj, zasieg, **kw):
    """Pomocnik: wymusza wspólny rodzaj+zasięg, żeby kary się nie liczyły
    nieumyślnie."""
    kw.setdefault("rodzaj", rodzaj)
    kw.setdefault("zasieg", zasieg)
    return baker.make(Zrodlo, **kw)


@pytest.mark.django_db
def test_score_zero_dla_zrodel_bez_zadnego_dopasowania(rodzaj, zasieg):
    a = _make_zrodlo(rodzaj, zasieg, nazwa="Foo Journal", skrot="FJ", issn="11112222")
    b = _make_zrodlo(rodzaj, zasieg, nazwa="Bar Magazine", skrot="BM", issn="33334444")
    # Żaden wskaźnik dopasowania ani kary — score == 0.
    assert ocen_podobienstwo(a, b) == 0


@pytest.mark.django_db
def test_identyczny_issn_daje_100(rodzaj, zasieg):
    a = _make_zrodlo(rodzaj, zasieg, nazwa="A", skrot="A", issn="1234-5678")
    b = _make_zrodlo(rodzaj, zasieg, nazwa="B", skrot="B", issn="1234-5678")
    assert ocen_podobienstwo(a, b) == 100


@pytest.mark.django_db
def test_identyczny_e_issn_daje_100(rodzaj, zasieg):
    a = _make_zrodlo(rodzaj, zasieg, nazwa="A", skrot="A", e_issn="1234-5678")
    b = _make_zrodlo(rodzaj, zasieg, nazwa="B", skrot="B", e_issn="1234-5678")
    assert ocen_podobienstwo(a, b) == 100


@pytest.mark.django_db
def test_oba_issn_daja_220_z_bonusem(rodzaj, zasieg):
    """100 (ISSN) + 100 (E-ISSN) + 20 (bonus za oba)."""
    a = _make_zrodlo(
        rodzaj, zasieg, nazwa="A", skrot="A", issn="1234-5678", e_issn="2222-3333"
    )
    b = _make_zrodlo(
        rodzaj, zasieg, nazwa="B", skrot="B", issn="1234-5678", e_issn="2222-3333"
    )
    assert ocen_podobienstwo(a, b) == 220


@pytest.mark.django_db
def test_identyczna_nazwa_po_normalizacji_daje_60(rodzaj, zasieg):
    """Nazwy mogą się różnić wielkością liter / białymi znakami — po
    normalizacji uznawane za identyczne."""
    a = _make_zrodlo(rodzaj, zasieg, nazwa="Acta Biochimica Polonica", skrot="ABP")
    b = _make_zrodlo(rodzaj, zasieg, nazwa="ACTA  BIOCHIMICA   POLONICA", skrot="abp")
    score = ocen_podobienstwo(a, b)
    # 60 za identyczną znormalizowaną nazwę. Trigram skrótu może dać +10.
    assert score in (60, 70)


@pytest.mark.django_db
def test_kara_za_rozny_rodzaj_zrodla(rodzaj, zasieg):
    """Gdy oba źródła mają ustawiony rodzaj_id i są one różne — -15."""
    inny_rodzaj = Rodzaj_Zrodla.objects.create(nazwa="Inny rodzaj")

    a = _make_zrodlo(rodzaj, zasieg, nazwa="A", skrot="A", issn="1234-5678")
    b = _make_zrodlo(inny_rodzaj, zasieg, nazwa="B", skrot="B", issn="1234-5678")
    # 100 (ISSN) - 15 (różny rodzaj) = 85
    assert ocen_podobienstwo(a, b) == 85


@pytest.mark.django_db
def test_kara_za_rozny_zasieg_zrodla(rodzaj, zasieg):
    """Gdy oba źródła mają ustawiony zasieg_id i są one różne — -10."""
    inny_zasieg = Zasieg_Zrodla.objects.create(nazwa="Międzynarodowy")

    a = _make_zrodlo(rodzaj, zasieg, nazwa="A", skrot="A", issn="1234-5678")
    b = _make_zrodlo(rodzaj, inny_zasieg, nazwa="B", skrot="B", issn="1234-5678")
    # 100 (ISSN) - 10 (różny zasięg) = 90
    assert ocen_podobienstwo(a, b) == 90


@pytest.mark.django_db
def test_pusty_issn_nie_daje_falszywego_dopasowania(rodzaj, zasieg):
    """Dwa źródła z ISSN="" nie powinny dawać 100 punktów."""
    a = _make_zrodlo(rodzaj, zasieg, nazwa="A", skrot="A", issn="")
    b = _make_zrodlo(rodzaj, zasieg, nazwa="B", skrot="B", issn="")
    assert ocen_podobienstwo(a, b) == 0


@pytest.mark.django_db
def test_score_jest_addytywny(rodzaj, zasieg):
    """ISSN (100) + identyczna nazwa (60) = 160 (plus ewentualnie trigram
    skrótu)."""
    a = _make_zrodlo(
        rodzaj, zasieg, nazwa="Acta Biochimica", skrot="AB", issn="1234-5678"
    )
    b = _make_zrodlo(
        rodzaj, zasieg, nazwa="Acta Biochimica", skrot="AB", issn="1234-5678"
    )
    score = ocen_podobienstwo(a, b)
    # 100 + 60 = 160 gwarantowane; identyczny skrót dorzuci +10
    assert score >= 160
    assert score <= 170

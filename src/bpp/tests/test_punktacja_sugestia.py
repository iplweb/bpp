from decimal import Decimal

import pytest
from model_bakery import baker

from bpp.punktacja_sugestia import (
    RodzajBraku,
    zaproponuj_punkty_ciagle,
    zaproponuj_punkty_zwarte,
)


def test_zwarte_monografia_autorska_poziom_II():
    s = zaproponuj_punkty_zwarte(
        poziom=2, ksiazka=True, rozdzial=False, autorstwo=True, redakcja=False
    )
    assert s.punkty == Decimal(200)
    assert s.rodzaj_braku is None


def test_zwarte_monografia_redagowana_poziom_II():
    s = zaproponuj_punkty_zwarte(
        poziom=2, ksiazka=True, rozdzial=False, autorstwo=False, redakcja=True
    )
    assert s.punkty == Decimal(100)


def test_zwarte_rozdzial_poziom_I():
    s = zaproponuj_punkty_zwarte(
        poziom=1, ksiazka=False, rozdzial=True, autorstwo=True, redakcja=False
    )
    assert s.punkty == Decimal(20)


def test_zwarte_poziom_brak_traktowany_jako_zero():
    for poziom in (-1, None):
        s = zaproponuj_punkty_zwarte(
            poziom=poziom, ksiazka=True, rozdzial=False, autorstwo=True, redakcja=False
        )
        assert s.punkty == Decimal(20)


def test_zwarte_brak_autorstwa():
    s = zaproponuj_punkty_zwarte(
        poziom=2, ksiazka=True, rozdzial=False, autorstwo=False, redakcja=False
    )
    assert s.punkty is None
    assert s.rodzaj_braku == RodzajBraku.BRAK_AUTORSTWA


def test_zwarte_nieobsluzona_kombinacja():
    s = zaproponuj_punkty_zwarte(
        poziom=2, ksiazka=True, rozdzial=True, autorstwo=True, redakcja=False
    )
    assert s.punkty is None
    assert s.rodzaj_braku == RodzajBraku.NIEOBSLUZONA_KOMBINACJA


@pytest.mark.django_db
def test_ciagle_jest_punktacja_zrodla():
    from bpp.models import Punktacja_Zrodla, Zrodlo

    zrodlo = baker.make(Zrodlo)
    baker.make(Punktacja_Zrodla, zrodlo=zrodlo, rok=2024, punkty_kbn=Decimal(140))
    s = zaproponuj_punkty_ciagle(zrodlo, 2024)
    assert s.punkty == Decimal(140)
    assert s.rodzaj_braku is None


@pytest.mark.django_db
def test_ciagle_brak_punktacji_zrodla_bez_fallbacku():
    from bpp.models import Zrodlo

    zrodlo = baker.make(Zrodlo)
    s = zaproponuj_punkty_ciagle(zrodlo, 2024)
    assert s.punkty is None  # NIE 5 pkt (to polityka komendy PBN, nie importera)
    assert s.rodzaj_braku == RodzajBraku.BRAK_DANYCH_ZRODLA


@pytest.mark.django_db
def test_ciagle_brak_roku():
    from bpp.models import Zrodlo

    s = zaproponuj_punkty_ciagle(baker.make(Zrodlo), None)
    assert s.punkty is None
    assert s.rodzaj_braku == RodzajBraku.BRAK_ROKU

"""
Testy obiektów zapytań multiseek związanych z jednostkami i wydziałami.

Ten moduł zawiera testy dla QueryObject dotyczących organizacji:
- JednostkaQueryObject - wyszukiwanie po jednostce
- WydzialQueryObject - wyszukiwanie po wydziale
- PierwszyWydzialQueryObject - wyszukiwanie po pierwszym wydziale
- PierwszaJednostkaQueryObject - wyszukiwanie po pierwszej jednostce
- AktualnaJednostkaAutoraQueryObject - wyszukiwanie po aktualnej jednostce autora
- ObcaJednostkaQueryObject - wyszukiwanie po obcej jednostce
- RodzajJednostkiQueryObject - wyszukiwanie po rodzaju jednostki
- KierunekStudiowQueryObject - wyszukiwanie po kierunku studiów
"""

import pytest
from multiseek import logic

from bpp.models.cache import Rekord
from bpp.multiseek_registry import (
    EQUAL_PLUS_SUB_FEMALE,
    EQUAL_PLUS_SUB_UNION_FEMALE,
    UNION,
    AktualnaJednostkaAutoraQueryObject,
    JednostkaQueryObject,
    KierunekStudiowQueryObject,
    ObcaJednostkaQueryObject,
    PierwszaJednostkaQueryObject,
    PierwszyWydzialQueryObject,
    RodzajJednostkiQueryObject,
    WydzialQueryObject,
)

pytestmark = pytest.mark.serial


def test_JednostkaQueryObject(jednostka):
    n = JednostkaQueryObject()

    ret = n.real_query(jednostka, logic.EQUAL)
    assert ret is not None

    ret = n.real_query(jednostka, logic.DIFFERENT)
    assert ret is not None

    ret = n.real_query(jednostka, UNION)
    assert ret is not None

    ret = n.real_query(None, logic.EQUAL)
    assert ret is not None

    ret = n.real_query(None, logic.DIFFERENT)
    assert ret is not None

    ret = n.real_query(None, UNION)
    assert ret is not None

    ret = n.real_query(jednostka, EQUAL_PLUS_SUB_FEMALE)
    assert ret is not None

    ret = n.real_query(jednostka, EQUAL_PLUS_SUB_UNION_FEMALE)
    assert ret is not None


def test_WydzialQueryObject(wydzial):
    # Faza B (#438): „wydział" w multiseeku to jednostka-korzeń (self-FK),
    # więc real_query przyjmuje root-Jednostkę (węzeł-lustro), nie Wydzial.
    from bpp.models.struktura_konwersja import znajdz_lub_utworz_wezel_wydzialu

    root, _ = znajdz_lub_utworz_wezel_wydzialu(wydzial)
    n = WydzialQueryObject()

    ret = n.real_query(root, logic.EQUAL)
    Rekord.objects.filter(ret)

    ret = n.real_query(root, logic.DIFFERENT)
    Rekord.objects.filter(ret)

    ret = n.real_query(root, UNION)
    Rekord.objects.filter(ret)

    ret = n.real_query(None, logic.EQUAL)
    Rekord.objects.filter(ret)

    ret = n.real_query(None, logic.DIFFERENT)
    Rekord.objects.filter(ret)

    ret = n.real_query(None, UNION)
    Rekord.objects.filter(ret)


def test_PierwszyWydzialQueryObject(wydzial):
    from bpp.models.struktura_konwersja import znajdz_lub_utworz_wezel_wydzialu

    root, _ = znajdz_lub_utworz_wezel_wydzialu(wydzial)
    n = PierwszyWydzialQueryObject()

    ret = n.real_query(root, logic.EQUAL)
    Rekord.objects.filter(ret)

    ret = n.real_query(root, logic.DIFFERENT)
    Rekord.objects.filter(ret)

    ret = n.real_query(root, UNION)
    Rekord.objects.filter(ret)

    ret = n.real_query(None, logic.EQUAL)
    Rekord.objects.filter(ret)

    ret = n.real_query(None, logic.DIFFERENT)
    Rekord.objects.filter(ret)

    ret = n.real_query(None, UNION)
    Rekord.objects.filter(ret)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "logic_arg",
    [logic.EQUAL, UNION, EQUAL_PLUS_SUB_FEMALE, EQUAL_PLUS_SUB_UNION_FEMALE],
)
def test_PierwszaJednostka_realQuery(
    wydawnictwo_zwarte, autor_jan_kowalski, jednostka, logic_arg
):
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)

    r = Rekord.objects.filter(
        PierwszaJednostkaQueryObject().real_query(jednostka, logic_arg)
    )

    assert len(r) == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "param",
    [
        logic.EQUAL,
        logic.DIFFERENT,
        EQUAL_PLUS_SUB_FEMALE,
    ],
)
def test_AktualnaJednostkaAutoraQueryObject(jednostka, param):
    res = AktualnaJednostkaAutoraQueryObject().real_query(jednostka, param)
    assert res is not None


@pytest.mark.django_db
def test_ObcaJednostkaQueryObject(
    wydawnictwo_zwarte,
    autor_jan_kowalski,
    obca_jednostka,
):
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, obca_jednostka, afiliuje=False)

    res = ObcaJednostkaQueryObject().real_query(True, logic.EQUAL)
    assert Rekord.objects.filter(res).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "param",
    [
        logic.EQUAL,
        logic.DIFFERENT,
    ],
)
def test_RodzajJednostkiQueryObject(param):
    # Faza B (#438), III-1: wartość to nazwa słownikowa ``RodzajJednostki``
    # (FK), nie kod starego CharField.
    ret = RodzajJednostkiQueryObject().real_query("Standard", param)
    assert Rekord.objects.filter(*(ret,)).count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "param",
    [
        logic.EQUAL,
        logic.DIFFERENT,
    ],
)
def test_KierunekStudiowQueryObject(param, kierunek_studiow):
    ret = KierunekStudiowQueryObject().real_query(kierunek_studiow, param)
    assert Rekord.objects.filter(*(ret,)).count() == 0

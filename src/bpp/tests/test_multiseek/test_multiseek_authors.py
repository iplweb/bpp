"""
Testy obiektów zapytań multiseek związanych z autorami.

Ten moduł zawiera testy dla QueryObject dotyczących autorów:
- NazwiskoIImieQueryObject - wyszukiwanie po nazwisku i imieniu autora
- Typ_OdpowiedzialnosciQueryObject - wyszukiwanie po typie odpowiedzialności
- TypOgolnyAutorQueryObject - wyszukiwanie autorów
- TypOgolnyRedaktorQueryObject - wyszukiwanie redaktorów
- TypOgolnyTlumaczQueryObject - wyszukiwanie tłumaczy
- TypOgolnyRecenzentQueryObject - wyszukiwanie recenzentów
- OstatnieNazwiskoIImie - wyszukiwanie po ostatnim nazwisku
- PierwszeNazwiskoIImie - wyszukiwanie po pierwszym nazwisku
- OswiadczenieKENQueryObject - wyszukiwanie po oświadczeniu KEN
"""

import pytest
from model_bakery import baker
from multiseek import logic

from bpp import const
from bpp.models import Typ_Odpowiedzialnosci
from bpp.models.cache import Rekord
from bpp.multiseek_registry import (
    UNION,
    NazwiskoIImieQueryObject,
    OstatnieNazwiskoIImie,
    OswiadczenieKENQueryObject,
    PierwszeNazwiskoIImie,
    Typ_OdpowiedzialnosciQueryObject,
    TypOgolnyAutorQueryObject,
    TypOgolnyRecenzentQueryObject,
    TypOgolnyRedaktorQueryObject,
    TypOgolnyTlumaczQueryObject,
)

pytestmark = pytest.mark.serial


def test_NazwiskoIImieQueryObject(autor_jan_nowak):
    n = NazwiskoIImieQueryObject()

    ret = n.real_query(autor_jan_nowak, logic.EQUAL)
    assert ret is not None

    ret = n.real_query(autor_jan_nowak, logic.DIFFERENT)
    assert ret is not None

    ret = n.real_query(autor_jan_nowak, UNION)
    assert ret is not None

    ret = n.real_query(None, logic.EQUAL)
    assert ret is not None

    ret = n.real_query(None, logic.DIFFERENT)
    assert ret is not None

    ret = n.real_query(None, UNION)
    assert ret is not None


@pytest.mark.django_db
@pytest.mark.parametrize("logic_arg", [logic.EQUAL, UNION])
def test_PierwszeNazwiskoIImie_real_query(
    wydawnictwo_zwarte, autor_jan_kowalski, jednostka, logic_arg
):
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)

    r = Rekord.objects.filter(
        PierwszeNazwiskoIImie().real_query(autor_jan_kowalski, logic_arg)
    )

    assert len(r) == 1


@pytest.mark.django_db
@pytest.mark.parametrize("logic_arg", [logic.EQUAL, UNION])
def test_PierwszeNazwiskoIImie_real_query_2(logic_arg):
    r = Rekord.objects.filter(PierwszeNazwiskoIImie().real_query(None, logic_arg))

    assert len(r) == 0


@pytest.mark.django_db
def test_Typ_OdpowiedzialnosciQueryObject():
    t = baker.make(Typ_Odpowiedzialnosci, typ_ogolny=const.TO_AUTOR)

    res = Typ_OdpowiedzialnosciQueryObject().real_query(t, logic.DIFFERENT)
    assert Rekord.objects.filter(res).count() == 0

    res = Typ_OdpowiedzialnosciQueryObject().real_query(t, logic.DIFFERENT)
    assert Rekord.objects.filter(res).count() == 0

    res = Typ_OdpowiedzialnosciQueryObject().real_query(None, logic.DIFFERENT)
    assert Rekord.objects.filter(res).count() == 0

    res = Typ_OdpowiedzialnosciQueryObject().real_query(None, UNION)
    assert Rekord.objects.filter(res).count() == 0


@pytest.mark.django_db
def test_TypOgolnyAutorQueryObject(autor_jan_nowak):
    baker.make(Typ_Odpowiedzialnosci, typ_ogolny=const.TO_AUTOR)

    res = TypOgolnyAutorQueryObject().real_query(autor_jan_nowak, logic.DIFFERENT)
    assert Rekord.objects.filter(res).count() == 0

    res = TypOgolnyAutorQueryObject().real_query(autor_jan_nowak, UNION)
    assert Rekord.objects.filter(res).count() == 0

    res = TypOgolnyAutorQueryObject().real_query(None, logic.DIFFERENT)
    assert Rekord.objects.filter(res).count() == 0

    res = TypOgolnyAutorQueryObject().real_query(None, UNION)
    assert Rekord.objects.filter(res).count() == 0


@pytest.mark.django_db
def test_TypOgolnyRedaktorQueryObject(autor_jan_nowak):
    baker.make(Typ_Odpowiedzialnosci, typ_ogolny=const.TO_REDAKTOR)

    res = TypOgolnyRedaktorQueryObject().real_query(autor_jan_nowak, logic.DIFFERENT)
    assert Rekord.objects.filter(res).count() == 0

    res = TypOgolnyRedaktorQueryObject().real_query(autor_jan_nowak, UNION)
    assert Rekord.objects.filter(res).count() == 0


@pytest.mark.django_db
def test_TypOgolnyTlumaczQueryObject(autor_jan_nowak):
    baker.make(Typ_Odpowiedzialnosci, typ_ogolny=const.TO_TLUMACZ)

    res = TypOgolnyTlumaczQueryObject().real_query(autor_jan_nowak, logic.DIFFERENT)
    assert Rekord.objects.filter(res).count() == 0

    res = TypOgolnyTlumaczQueryObject().real_query(autor_jan_nowak, UNION)
    assert Rekord.objects.filter(res).count() == 0


@pytest.mark.django_db
def test_TypOgolnyRecenzentQueryObject(autor_jan_nowak):
    baker.make(Typ_Odpowiedzialnosci, typ_ogolny=const.TO_RECENZENT)

    res = TypOgolnyRecenzentQueryObject().real_query(autor_jan_nowak, logic.DIFFERENT)
    assert Rekord.objects.filter(res).count() == 0

    res = TypOgolnyRecenzentQueryObject().real_query(autor_jan_nowak, UNION)
    assert Rekord.objects.filter(res).count() == 0


@pytest.mark.django_db
def test_OstatnieNazwiskoIImie(autor_jan_nowak):
    res = OstatnieNazwiskoIImie().real_query(autor_jan_nowak, logic.DIFFERENT)
    assert Rekord.objects.filter(res).count() == 0


@pytest.mark.django_db
def test_Typ_OdpowiedzialnosciQueryObject_value_from_web_missing():
    """Test that value_from_web returns None for non-existent Typ_Odpowiedzialnosci."""
    result = Typ_OdpowiedzialnosciQueryObject().value_from_web(
        "non-existent-nazwa-xyz-123"
    )
    assert result is None


@pytest.mark.django_db
def test_Typ_OdpowiedzialnosciQueryObject_value_from_web_existing():
    """Test that value_from_web returns the object for existing Typ_Odpowiedzialnosci."""
    t = baker.make(Typ_Odpowiedzialnosci, nazwa="test-typ-odpowiedzialnosci")
    result = Typ_OdpowiedzialnosciQueryObject().value_from_web(
        "test-typ-odpowiedzialnosci"
    )
    assert result == t


@pytest.mark.django_db
@pytest.mark.parametrize(
    "param",
    [
        logic.EQUAL,
        logic.DIFFERENT,
    ],
)
@pytest.mark.parametrize("value", [True, False, None])
def test_OswiadczenieKENQueryObject(param, value):
    ret = OswiadczenieKENQueryObject().real_query(value, param)
    assert Rekord.objects.filter(*(ret,)).count() == 0

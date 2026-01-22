"""
Testy podstawowych obiektów zapytań multiseek.

Ten moduł zawiera testy dla podstawowych QueryObject:
- TytulPracyQueryObject - wyszukiwanie po tytule pracy
- StronaWWWUstawionaQueryObject - sprawdzanie czy strona WWW jest ustawiona
- LicencjaOpenAccessUstawionaQueryObject - sprawdzanie licencji OpenAccess
- CharakterOgolnyQueryObject - wyszukiwanie po charakterze ogólnym
- DataUtworzeniaQueryObject - wyszukiwanie po dacie utworzenia
- DyscyplinaQueryObject - wyszukiwanie po dyscyplinie naukowej
- OpenaccessWersjaTekstuQueryObject, OpenaccessLicencjaQueryObject,
  OpenaccessCzasPublikacjiQueryObject - wyszukiwanie po parametrach OpenAccess
- ForeignKeyDescribeMixin - mixin do opisywania kluczy obcych
- CharakterFormalnyQueryObject - wyszukiwanie po charakterze formalnym
- JezykQueryObject - wyszukiwanie po języku
"""

from datetime import datetime

import pytest
from model_bakery import baker
from multiseek import logic
from multiseek.logic import DIFFERENT, EQUAL, AutocompleteQueryObject

from bpp.models import (
    Autor_Dyscyplina,
    Charakter_Formalny,
    Dyscyplina_Naukowa,
    Jezyk,
)
from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.openaccess import (
    Czas_Udostepnienia_OpenAccess,
    Licencja_OpenAccess,
    Wersja_Tekstu_OpenAccess,
)
from bpp.multiseek_registry import (
    CharakterFormalnyQueryObject,
    CharakterOgolnyQueryObject,
    DataUtworzeniaQueryObject,
    DyscyplinaQueryObject,
    ForeignKeyDescribeMixin,
    JezykQueryObject,
    LicencjaOpenAccessUstawionaQueryObject,
    OpenaccessCzasPublikacjiQueryObject,
    OpenaccessLicencjaQueryObject,
    OpenaccessWersjaTekstuQueryObject,
    StronaWWWUstawionaQueryObject,
    TytulPracyQueryObject,
)

pytestmark = pytest.mark.serial


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["foo", "bar", "łódź", "jeszcze test"])
@pytest.mark.parametrize(
    "operation",
    [
        logic.CONTAINS,
        logic.NOT_CONTAINS,
        logic.STARTS_WITH,
        logic.NOT_STARTS_WITH,
        logic.EQUAL,
    ],
)
def test_TytulPracyQueryObject(value, operation):
    ret = TytulPracyQueryObject(
        field_name="tytul_oryginalny", label="Tytuł oryginalny", public=True
    ).real_query(value, operation)
    assert Rekord.objects.filter(*(ret,)).count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("tested_field", ["www", "public_www"])
def test_StronaWWWUstawionaQueryObject_jedna_z(wydawnictwo_zwarte, tested_field):
    fields = ["public_www", "www"]
    for field in fields:
        setattr(wydawnictwo_zwarte, field, "")
    wydawnictwo_zwarte.save()

    qry = StronaWWWUstawionaQueryObject("x1x").real_query(True, logic.EQUAL_FEMALE)
    assert Rekord.objects.filter(*(qry,)).count() == 0

    qry = StronaWWWUstawionaQueryObject("x1x").real_query(False, logic.EQUAL_FEMALE)
    assert Rekord.objects.filter(*(qry,)).count() == 1

    setattr(wydawnictwo_zwarte, tested_field, "http://onet.pl/")
    wydawnictwo_zwarte.save()

    qry = StronaWWWUstawionaQueryObject("x1x").real_query(True, logic.EQUAL_FEMALE)
    assert Rekord.objects.filter(*(qry,)).count() == 1

    qry = StronaWWWUstawionaQueryObject("x1x").real_query(False, logic.EQUAL_FEMALE)
    assert Rekord.objects.filter(*(qry,)).count() == 0


@pytest.mark.django_db
def test_StronaWWWUstawionaQueryObject_obydwie_strony(
    wydawnictwo_zwarte,
):
    fields = ["public_www", "www"]
    for field in fields:
        setattr(wydawnictwo_zwarte, field, "http://onet.pl/")
    wydawnictwo_zwarte.save()

    qry = StronaWWWUstawionaQueryObject("x1x").real_query(True, logic.EQUAL_FEMALE)
    assert Rekord.objects.filter(*(qry,)).count() == 1


@pytest.mark.django_db
def test_multiseek_licencja_openaccess_ustawiona(wydawnictwo_zwarte):
    lqo = LicencjaOpenAccessUstawionaQueryObject(
        field_name="licencja_openaccess", label="X", public=True
    )
    res = lqo.real_query(True, logic.EQUAL)
    assert Rekord.objects.filter(*(res,)).count() == 0

    res = lqo.real_query(False, logic.EQUAL)
    assert Rekord.objects.filter(*(res,)).count() == 1


@pytest.mark.django_db
def test_multiseek_charakter_formalny_ogolny(wydawnictwo_zwarte, ksiazka_polska):
    wydawnictwo_zwarte.charakter_formalny = ksiazka_polska
    wydawnictwo_zwarte.save()

    lqo = CharakterOgolnyQueryObject(field_name="charakter", label="X")
    res = lqo.real_query("książka", logic.EQUAL)
    assert Rekord.objects.filter(*(res,)).count() == 1

    res = lqo.real_query("książka", logic.DIFFERENT)
    assert Rekord.objects.filter(*(res,)).count() == 0


def test_DataUtworzeniaQueryObject():
    d = DataUtworzeniaQueryObject()
    assert d.value_for_description('[""]') == str(datetime.now().date())
    assert d.value_for_description('["2018-01-01 12:00:00"]') == "2018-01-01"
    assert (
        d.value_for_description('["2018-01-01 12:00:00", "2018-01-01 12:00:00"]')
        == "od 2018-01-01 do 2018-01-01"
    )


@pytest.mark.django_db
def test_DyscyplinaQueryObject(autor_jan_kowalski, wydawnictwo_zwarte, rok, jednostka):
    dn = baker.make(Dyscyplina_Naukowa)
    ad, created = Autor_Dyscyplina.objects.get_or_create(
        autor=autor_jan_kowalski, rok=rok, defaults={"dyscyplina_naukowa": dn}
    )
    if not created:
        ad.dyscyplina_naukowa = dn
        ad.save()
    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_kowalski, jednostka, dyscyplina_naukowa=dn
    )

    res = DyscyplinaQueryObject().real_query(dn, EQUAL)
    assert Rekord.objects.filter(res).count() == 1

    res = DyscyplinaQueryObject().real_query(dn, DIFFERENT)
    assert Rekord.objects.filter(res).count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "klass,model",
    [
        (OpenaccessWersjaTekstuQueryObject, Wersja_Tekstu_OpenAccess),
        (OpenaccessLicencjaQueryObject, Licencja_OpenAccess),
        (OpenaccessCzasPublikacjiQueryObject, Czas_Udostepnienia_OpenAccess),
    ],
)
def test_multiseek_openaccess(klass, model, openaccess_data):
    f = model.objects.all().first()
    x = klass().value_from_web(f.nazwa)
    assert f == x


@pytest.mark.django_db
def test_ForeignKeyDescribeMixin_value_for_description():
    class Tst(ForeignKeyDescribeMixin, AutocompleteQueryObject):
        field_name = "foo"
        model = Autor

    x = Tst()
    assert x.value_for_description("123").find("został usunięty") > 0


@pytest.mark.django_db
def test_CharakterFormalnyQueryObject_value_from_web_missing():
    """Test that value_from_web returns None for non-existent Charakter_Formalny."""
    result = CharakterFormalnyQueryObject().value_from_web(
        "non-existent-charakter-xyz-123"
    )
    assert result is None


@pytest.mark.django_db
def test_CharakterFormalnyQueryObject_value_from_web_existing(charaktery_formalne):
    """Test that value_from_web returns the object for existing Charakter_Formalny."""
    cf = Charakter_Formalny.objects.first()
    result = CharakterFormalnyQueryObject().value_from_web(cf.nazwa)
    assert result == cf


@pytest.mark.django_db
def test_CharakterFormalnyQueryObject_value_from_web_none():
    """Test that value_from_web returns None when value is None."""
    result = CharakterFormalnyQueryObject().value_from_web(None)
    assert result is None


@pytest.mark.django_db
def test_CharakterFormalnyQueryObject_real_query_none():
    """Test that real_query returns empty Q object when value is None.

    This handles the case when a user selects a Charakter_Formalny that no longer
    exists in the database - the query should return no results instead of crashing.
    """
    qobj = CharakterFormalnyQueryObject()
    result = qobj.real_query(None, str(EQUAL))
    # The result should be a Q object that matches no records
    from bpp.models.cache import Rekord

    assert Rekord.objects.filter(*(result,)).count() == 0


@pytest.mark.django_db
def test_JezykQueryObject_value_from_web_missing():
    """Test that value_from_web returns None for non-existent Jezyk."""
    result = JezykQueryObject().value_from_web("non-existent-jezyk-xyz-123")
    assert result is None


@pytest.mark.django_db
def test_JezykQueryObject_value_from_web_existing(jezyki):
    """Test that value_from_web returns the object for existing Jezyk."""
    j = Jezyk.objects.first()
    result = JezykQueryObject().value_from_web(j.nazwa)
    assert result == j

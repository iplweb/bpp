# -*- encoding: utf-8 -*-
from datetime import datetime

import pytest
from model_mommy import mommy
from multiseek import logic
from multiseek.logic import AutocompleteQueryObject

from bpp.models import Dyscyplina_Naukowa, Zewnetrzna_Baza_Danych, Typ_Odpowiedzialnosci, Jezyk, Charakter_Formalny, \
    Typ_KBN
from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.openaccess import Wersja_Tekstu_OpenAccess, \
    Licencja_OpenAccess, Czas_Udostepnienia_OpenAccess
from bpp.multiseek_registry import TytulPracyQueryObject, \
    OpenaccessWersjaTekstuQueryObject, OpenaccessLicencjaQueryObject, \
    OpenaccessCzasPublikacjiQueryObject, ForeignKeyDescribeMixin, PierwszeNazwiskoIImie, DataUtworzeniaQueryObject, \
    NazwiskoIImieQueryObject, DyscyplinaAutoraQueryObject, ZewnetrznaBazaDanychQueryObject, JednostkaQueryObject, \
    WydzialQueryObject, Typ_OdpowiedzialnosciQueryObject, JezykQueryObject, TypRekorduObject, \
    CharakterFormalnyQueryObject, TypKBNQueryObject


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["foo", "bar", "łódź", "jeszcze test"])
@pytest.mark.parametrize("operation",
                         [logic.CONTAINS,
                          logic.NOT_CONTAINS,
                          logic.STARTS_WITH,
                          logic.NOT_STARTS_WITH,
                          logic.EQUAL])
def test_TytulPracyQueryObject(value, operation):
    ret = TytulPracyQueryObject(
        field_name='tytul_oryginalny',
        label="Tytuł oryginalny",
        public=True
    ).real_query(value, operation)
    assert Rekord.objects.filter(*(ret,)).count() == 0


def test_DataUtworzeniaQueryObject():
    d = DataUtworzeniaQueryObject()
    assert d.value_for_description('[""]') == str(datetime.now().date())
    d.value_for_description('["2018-01-01 12:00:00"]') == "2018-01-01"
    d.value_for_description('["2018-01-01 12:00:00", "2018-01-01 12:00:00"]') == "od 2018-01-01 do 2018-01-01"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "klass,model",
    [(OpenaccessWersjaTekstuQueryObject,
      Wersja_Tekstu_OpenAccess),
     (OpenaccessLicencjaQueryObject,
      Licencja_OpenAccess),
     (OpenaccessCzasPublikacjiQueryObject,
      Czas_Udostepnienia_OpenAccess)])
def test_multiseek_openaccess(klass, model, openaccess_data):
    f = model.objects.all().first()
    x = klass().value_from_web(f.nazwa)
    assert f == x


@pytest.mark.django_db
def test_ForeignKeyDescribeMixin_value_for_description():
    class Tst(ForeignKeyDescribeMixin, AutocompleteQueryObject):
        field_name = 'foo'
        model = Autor

    x = Tst()
    assert x.value_for_description("123").find("został usunięty") > 0


def test_NazwiskoIImieQueryObject(autor_jan_nowak):
    n = NazwiskoIImieQueryObject()
    ret = n.real_query(autor_jan_nowak, logic.DIFFERENT)
    assert ret is not None


@pytest.mark.django_db
def test_PierwszeNazwiskoIImie_real_query(wydawnictwo_zwarte, autor_jan_kowalski, jednostka):
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)

    r = Rekord.objects.filter(
        PierwszeNazwiskoIImie().real_query(autor_jan_kowalski.pk, logic.EQUAL)
    )

    assert len(r) == 1

    r = Rekord.objects.filter(
        PierwszeNazwiskoIImie().real_query(autor_jan_kowalski.pk, logic.DIFFERENT)
    )

    assert len(r) == 0


@pytest.mark.django_db
def test_DyscyplinaNaukowaAutoraQueryObject():
    d = DyscyplinaAutoraQueryObject()
    dyscyplina = mommy.make(Dyscyplina_Naukowa)
    res = d.real_query(dyscyplina, logic.DIFFERENT)
    assert res is not None


@pytest.mark.django_db
def test_ZewnetrznaBazaDanychQueryObject():
    d = mommy.make(Zewnetrzna_Baza_Danych)
    z = ZewnetrznaBazaDanychQueryObject()
    z.real_query(d, logic.DIFFERENT)


@pytest.mark.django_db
def test_JednostkaQueryObject(jednostka):
    z = JednostkaQueryObject()
    z.real_query(jednostka, logic.DIFFERENT)


@pytest.mark.django_db
def test_WydzialQueryObject(wydzial):
    z = WydzialQueryObject()
    z.real_query(wydzial, logic.DIFFERENT)


@pytest.mark.django_db
def test_Typ_OdpowiedzialnosciQueryObject():
    t = mommy.make(Typ_Odpowiedzialnosci)
    z = Typ_OdpowiedzialnosciQueryObject()
    z.real_query(t, logic.DIFFERENT)


@pytest.mark.django_db
def test_JezykQueryObject():
    j = mommy.make(Jezyk, nazwa="foo")
    assert j == JezykQueryObject().value_from_web("foo")


@pytest.mark.django_db
@pytest.mark.parametrize("typ_pracy", ["streszczenia", "publikacje", "inne"])
def test_TypRekorduObject(typ_pracy):
    t = TypRekorduObject()
    assert t.value_from_web(typ_pracy) == typ_pracy
    t.real_query(typ_pracy, logic.DIFFERENT)


@pytest.mark.django_db
def test_CharakterFormalnyQueryObject():
    cf = mommy.make(Charakter_Formalny)
    res = CharakterFormalnyQueryObject().real_query(cf, logic.DIFFERENT)
    assert res is not None



@pytest.mark.django_db
def test_TypKBNQueryObject():
    tk = mommy.make(Typ_KBN)
    res = TypKBNQueryObject().real_query(tk, logic.DIFFERENT)
    assert res is not None

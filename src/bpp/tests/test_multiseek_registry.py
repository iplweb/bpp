# -*- encoding: utf-8 -*-
from datetime import datetime

import pytest
from model_mommy import mommy
from multiseek import logic
from multiseek.logic import AutocompleteQueryObject, EQUAL

from bpp.models import Typ_Odpowiedzialnosci, const, Zewnetrzna_Baza_Danych, Dyscyplina_Naukowa, Autor_Dyscyplina
from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.openaccess import Wersja_Tekstu_OpenAccess, \
    Licencja_OpenAccess, Czas_Udostepnienia_OpenAccess
from bpp.multiseek_registry import TytulPracyQueryObject, \
    OpenaccessWersjaTekstuQueryObject, OpenaccessLicencjaQueryObject, \
    OpenaccessCzasPublikacjiQueryObject, ForeignKeyDescribeMixin, PierwszeNazwiskoIImie, \
    TypOgolnyAutorQueryObject, TypOgolnyRedaktorQueryObject, TypOgolnyTlumaczQueryObject, TypOgolnyRecenzentQueryObject, \
    NazwiskoIImieQueryObject, DataUtworzeniaQueryObject, OstatnieNazwiskoIImie, OstatnioZmieniony, \
    OstatnioZmienionyDlaPBN, RodzajKonferenckjiQueryObject, LiczbaAutorowQueryObject, UNION, JednostkaQueryObject, \
    WydzialQueryObject, ZewnetrznaBazaDanychQueryObject, Typ_OdpowiedzialnosciQueryObject, DyscyplinaAutoraQueryObject


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
def test_DyscyplinaAutoraQueryObject(autor_jan_kowalski):
    dn = mommy.make(Dyscyplina_Naukowa)
    ad = Autor_Dyscyplina.objects.create(autor=autor_jan_kowalski, dyscyplina_naukowa=dn, rok=2019)
    d = DyscyplinaAutoraQueryObject()
    res = d.real_query(dn, EQUAL)
    assert res


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


def test_WydzialQueryObject(wydzial):
    n = WydzialQueryObject()

    ret = n.real_query(wydzial, logic.EQUAL)
    assert ret is not None

    ret = n.real_query(wydzial, logic.DIFFERENT)
    assert ret is not None

    ret = n.real_query(wydzial, UNION)
    assert ret is not None

    ret = n.real_query(None, logic.EQUAL)
    assert ret is not None

    ret = n.real_query(None, logic.DIFFERENT)
    assert ret is not None

    ret = n.real_query(None, UNION)
    assert ret is not None


@pytest.mark.django_db
@pytest.mark.parametrize("logic_arg", [logic.EQUAL, UNION])
def test_PierwszeNazwiskoIImie_real_query(wydawnictwo_zwarte, autor_jan_kowalski, jednostka, logic_arg):
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)

    r = Rekord.objects.filter(
        PierwszeNazwiskoIImie().real_query(autor_jan_kowalski, logic_arg)
    )

    assert len(r) == 1


@pytest.mark.django_db
@pytest.mark.parametrize("logic_arg", [logic.EQUAL, UNION])
def test_PierwszeNazwiskoIImie_real_query(logic_arg):
    r = Rekord.objects.filter(
        PierwszeNazwiskoIImie().real_query(None, logic_arg)
    )

    assert len(r) == 0


@pytest.mark.django_db
def test_Typ_OdpowiedzialnosciQueryObject():
    t = mommy.make(Typ_Odpowiedzialnosci, typ_ogolny=const.TO_AUTOR)

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
    t = mommy.make(Typ_Odpowiedzialnosci, typ_ogolny=const.TO_AUTOR)

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
    t = mommy.make(Typ_Odpowiedzialnosci, typ_ogolny=const.TO_REDAKTOR)

    res = TypOgolnyRedaktorQueryObject().real_query(autor_jan_nowak, logic.DIFFERENT)
    assert Rekord.objects.filter(res).count() == 0

    res = TypOgolnyRedaktorQueryObject().real_query(autor_jan_nowak, UNION)
    assert Rekord.objects.filter(res).count() == 0


@pytest.mark.django_db
def test_TypOgolnyTlumaczQueryObject(autor_jan_nowak):
    t = mommy.make(Typ_Odpowiedzialnosci, typ_ogolny=const.TO_TLUMACZ)

    res = TypOgolnyTlumaczQueryObject().real_query(autor_jan_nowak, logic.DIFFERENT)
    assert Rekord.objects.filter(res).count() == 0

    res = TypOgolnyTlumaczQueryObject().real_query(autor_jan_nowak, UNION)
    assert Rekord.objects.filter(res).count() == 0


@pytest.mark.django_db
def test_TypOgolnyRecenzentQueryObject(autor_jan_nowak):
    t = mommy.make(Typ_Odpowiedzialnosci, typ_ogolny=const.TO_RECENZENT)

    res = TypOgolnyRecenzentQueryObject().real_query(autor_jan_nowak, logic.DIFFERENT)
    assert Rekord.objects.filter(res).count() == 0

    res = TypOgolnyRecenzentQueryObject().real_query(autor_jan_nowak, UNION)
    assert Rekord.objects.filter(res).count() == 0


@pytest.mark.django_db
def test_OstatnieNazwiskoIImie(autor_jan_nowak):
    res = OstatnieNazwiskoIImie().real_query(autor_jan_nowak, logic.DIFFERENT)
    assert Rekord.objects.filter(res).count() == 0


@pytest.mark.django_db
def test_OstatnioZmieniony():
    res = OstatnioZmieniony().real_query(datetime.now(), logic.EQUAL)
    assert Rekord.objects.filter(res).count() == 0


@pytest.mark.django_db
def test_OstatnioZmienionyDlaPBN():
    res = OstatnioZmienionyDlaPBN().real_query(datetime.now(), logic.EQUAL)
    assert Rekord.objects.filter(res).count() == 0


@pytest.mark.django_db
def test_RodzajKonferenckjiQueryObject():
    res = RodzajKonferenckjiQueryObject().real_query("krajowa", logic.DIFFERENT)
    assert Rekord.objects.filter(res).count() == 0


@pytest.mark.django_db
def test_LiczbaAutorowQueryObject():
    res = LiczbaAutorowQueryObject().real_query(5, logic.DIFFERENT)
    assert Rekord.objects.filter(res).count() == 0


@pytest.mark.django_db
def test_ZewnetrznaBazaDanychQueryObject():
    zbd = mommy.make(Zewnetrzna_Baza_Danych)
    res = ZewnetrznaBazaDanychQueryObject().real_query(zbd, logic.DIFFERENT)
    assert Rekord.objects.filter(res).count() == 0

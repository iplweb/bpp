from datetime import datetime

import pytest
from model_bakery import baker
from multiseek import logic
from multiseek.logic import DIFFERENT, EQUAL, AutocompleteQueryObject

from bpp import const
from bpp.models import (
    Autor_Dyscyplina,
    Dyscyplina_Naukowa,
    Jednostka,
    Typ_Odpowiedzialnosci,
    Zewnetrzna_Baza_Danych,
)
from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.openaccess import (
    Czas_Udostepnienia_OpenAccess,
    Licencja_OpenAccess,
    Wersja_Tekstu_OpenAccess,
)
from bpp.multiseek_registry import (
    EQUAL_PLUS_SUB_FEMALE,
    EQUAL_PLUS_SUB_UNION_FEMALE,
    UNION,
    AktualnaJednostkaAutoraQueryObject,
    CharakterOgolnyQueryObject,
    DataUtworzeniaQueryObject,
    DOIQueryObject,
    DyscyplinaQueryObject,
    ForeignKeyDescribeMixin,
    JednostkaQueryObject,
    KierunekStudiowQueryObject,
    LicencjaOpenAccessUstawionaQueryObject,
    LiczbaAutorowQueryObject,
    NazwiskoIImieQueryObject,
    ObcaJednostkaQueryObject,
    OpenaccessCzasPublikacjiQueryObject,
    OpenaccessLicencjaQueryObject,
    OpenaccessWersjaTekstuQueryObject,
    OstatnieNazwiskoIImie,
    OstatnioZmieniony,
    PierwszaJednostkaQueryObject,
    PierwszeNazwiskoIImie,
    PierwszyWydzialQueryObject,
    PublicDostepDniaQueryObject,
    RodzajJednostkiQueryObject,
    RodzajKonferenckjiQueryObject,
    SlowaKluczoweQueryObject,
    StronaWWWUstawionaQueryObject,
    Typ_OdpowiedzialnosciQueryObject,
    TypOgolnyAutorQueryObject,
    TypOgolnyRecenzentQueryObject,
    TypOgolnyRedaktorQueryObject,
    TypOgolnyTlumaczQueryObject,
    TytulPracyQueryObject,
    WydzialQueryObject,
    ZewnetrznaBazaDanychQueryObject,
)


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
        setattr(wydawnictwo_zwarte, field, None)
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
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, dyscyplina_naukowa=dn, rok=rok
    )
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

    ret = n.real_query(jednostka, EQUAL_PLUS_SUB_FEMALE)
    assert ret is not None

    ret = n.real_query(jednostka, EQUAL_PLUS_SUB_UNION_FEMALE)
    assert ret is not None


def test_WydzialQueryObject(wydzial):
    n = WydzialQueryObject()

    ret = n.real_query(wydzial, logic.EQUAL)
    Rekord.objects.filter(ret)

    ret = n.real_query(wydzial, logic.DIFFERENT)
    Rekord.objects.filter(ret)

    ret = n.real_query(wydzial, UNION)
    Rekord.objects.filter(ret)

    ret = n.real_query(None, logic.EQUAL)
    Rekord.objects.filter(ret)

    ret = n.real_query(None, logic.DIFFERENT)
    Rekord.objects.filter(ret)

    ret = n.real_query(None, UNION)
    Rekord.objects.filter(ret)


def test_PierwszyWydzialQueryObject(wydzial):
    n = PierwszyWydzialQueryObject()

    ret = n.real_query(wydzial, logic.EQUAL)
    Rekord.objects.filter(ret)

    ret = n.real_query(wydzial, logic.DIFFERENT)
    Rekord.objects.filter(ret)

    ret = n.real_query(wydzial, UNION)
    Rekord.objects.filter(ret)

    ret = n.real_query(None, logic.EQUAL)
    Rekord.objects.filter(ret)

    ret = n.real_query(None, logic.DIFFERENT)
    Rekord.objects.filter(ret)

    ret = n.real_query(None, UNION)
    Rekord.objects.filter(ret)


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
def test_OstatnioZmieniony():
    res = OstatnioZmieniony().real_query(datetime.now(), logic.EQUAL)
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
    zbd = baker.make(Zewnetrzna_Baza_Danych)
    res = ZewnetrznaBazaDanychQueryObject().real_query(zbd, logic.DIFFERENT)
    assert Rekord.objects.filter(res).count() == 0


@pytest.mark.django_db
def test_DOIQueryObject():
    res = DOIQueryObject().real_query("foo", logic.EQUAL)
    assert Rekord.objects.filter(res).count() == 0


@pytest.mark.django_db
def test_DostepDniaQueryObject():
    res = PublicDostepDniaQueryObject().real_query(True, logic.EQUAL)
    assert Rekord.objects.filter(res).count() == 0


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
def test_SlowaKluczoweQueryObject(wydawnictwo_zwarte):
    wydawnictwo_zwarte.slowa_kluczowe.add("foo")
    wydawnictwo_zwarte.save()

    res = SlowaKluczoweQueryObject().real_query("foo", logic.EQUAL)
    assert Rekord.objects.filter(res).count() == 1


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
@pytest.mark.parametrize(
    "param",
    [
        logic.EQUAL,
        logic.DIFFERENT,
    ],
)
def test_RodzajJednostkiQueryObject(param):
    ret = RodzajJednostkiQueryObject().real_query(
        Jednostka.RODZAJ_JEDNOSTKI.NORMALNA.label, param
    )
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

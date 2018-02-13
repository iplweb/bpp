# -*- encoding: utf-8 -*-
import pytest
from multiseek import logic

from bpp.models import Wydawnictwo_Zwarte
from bpp.models.autor import Autor
from multiseek.logic import CONTAINS, NOT_CONTAINS, STARTS_WITH, \
    NOT_STARTS_WITH, AutocompleteQueryObject

from bpp.models.cache import Rekord
from bpp.models.openaccess import Wersja_Tekstu_OpenAccess, \
    Licencja_OpenAccess, Czas_Udostepnienia_OpenAccess
from bpp.multiseek_registry import TytulPracyQueryObject, \
    OpenaccessWersjaTekstuQueryObject, OpenaccessLicencjaQueryObject, \
    OpenaccessCzasPublikacjiQueryObject, ForeignKeyDescribeMixin, PierwszeNazwiskoIImie


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["foo", "bar", "łódź"])
@pytest.mark.parametrize("operation",
                         [CONTAINS, NOT_CONTAINS,
                          STARTS_WITH, NOT_STARTS_WITH])
def test_TytulPracyQueryObject(value, operation):
    ret = TytulPracyQueryObject(
        field_name='tytul_oryginalny',
        label="Tytuł oryginalny",
        public=True
    ).real_query(value, operation)
    assert Rekord.objects.filter(*(ret,)).count() == 0


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


@pytest.mark.django_db
def test_PierwszeNazwiskoIImie_real_query(wydawnictwo_zwarte, autor_jan_kowalski, jednostka):
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)

    r = Rekord.objects.filter(
        PierwszeNazwiskoIImie().real_query(autor_jan_kowalski.pk, logic.EQUAL)
    )

    assert len(r) == 1
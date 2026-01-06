"""
Testy różnych obiektów zapytań multiseek.

Ten moduł zawiera testy dla pozostałych QueryObject:
- OstatnioZmieniony - wyszukiwanie po dacie ostatniej zmiany
- RodzajKonferenckjiQueryObject - wyszukiwanie po rodzaju konferencji
- LiczbaAutorowQueryObject - wyszukiwanie po liczbie autorów
- ZewnetrznaBazaDanychQueryObject - wyszukiwanie po zewnętrznej bazie danych
- DOIQueryObject - wyszukiwanie po DOI
- PublicDostepDniaQueryObject - wyszukiwanie po dacie dostępu publicznego
- SlowaKluczoweQueryObject - wyszukiwanie po słowach kluczowych
- StatusKorektyQueryObject - wyszukiwanie po statusie korekty
"""

from datetime import datetime

import pytest
from model_bakery import baker
from multiseek import logic

from bpp.models import Zewnetrzna_Baza_Danych
from bpp.models.cache import Rekord
from bpp.multiseek_registry import (
    DOIQueryObject,
    LiczbaAutorowQueryObject,
    OstatnioZmieniony,
    PublicDostepDniaQueryObject,
    RodzajKonferenckjiQueryObject,
    SlowaKluczoweQueryObject,
    StatusKorektyQueryObject,
    ZewnetrznaBazaDanychQueryObject,
)

pytestmark = pytest.mark.serial


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
    ],
)
def test_StatusKorektyQueryObject(param, statusy_korekt):
    ret = StatusKorektyQueryObject().real_query(statusy_korekt["przed korektą"], param)
    assert Rekord.objects.filter(*(ret,)).count() == 0

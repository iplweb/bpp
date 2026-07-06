"""Filtr admina po statusie powiązanej pracy PBN (``pbn_uid.status``).

Pozwala w adminie ``Wydawnictwo_Ciagle``/``Wydawnictwo_Zwarte`` wyłapać rekordy
powiązane z pracą skasowaną w PBN (``status == "DELETED"``), aktywną
(``ACTIVE``) albo bez powiązania (``pbn_uid`` puste).
"""

import pytest
from model_bakery import baker

from bpp.admin.filters import PBNStatusFilter
from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from pbn_api.models import Publication


def _pub(mongo_id, status):
    return baker.make(
        Publication,
        mongoId=mongo_id,
        versions=[{"current": True, "object": {"title": mongo_id}}],
        status=status,
    )


@pytest.fixture
def trzy_wydawnictwa_ciagle():
    """(deleted, active, brak) — po jednym Wydawnictwo_Ciagle każdego rodzaju."""
    wc_del = baker.make(Wydawnictwo_Ciagle, pbn_uid=_pub("wc_del", "DELETED"))
    wc_act = baker.make(Wydawnictwo_Ciagle, pbn_uid=_pub("wc_act", "ACTIVE"))
    wc_brak = baker.make(Wydawnictwo_Ciagle, pbn_uid=None)
    return wc_del, wc_act, wc_brak


def _apply(value, model):
    f = PBNStatusFilter(None, {}, model, None)
    f.value = lambda *a, **k: value
    return f.queryset(None, model.objects.all())


@pytest.mark.django_db
def test_filtr_deleted(trzy_wydawnictwa_ciagle):
    wc_del, wc_act, wc_brak = trzy_wydawnictwa_ciagle
    qs = _apply("deleted", Wydawnictwo_Ciagle)
    assert wc_del in qs
    assert wc_act not in qs
    assert wc_brak not in qs


@pytest.mark.django_db
def test_filtr_active(trzy_wydawnictwa_ciagle):
    wc_del, wc_act, wc_brak = trzy_wydawnictwa_ciagle
    qs = _apply("active", Wydawnictwo_Ciagle)
    assert wc_act in qs
    assert wc_del not in qs
    assert wc_brak not in qs


@pytest.mark.django_db
def test_filtr_brak(trzy_wydawnictwa_ciagle):
    wc_del, wc_act, wc_brak = trzy_wydawnictwa_ciagle
    qs = _apply("brak", Wydawnictwo_Ciagle)
    assert wc_brak in qs
    assert wc_del not in qs
    assert wc_act not in qs


@pytest.mark.django_db
def test_filtr_brak_wartosci_nie_zaweza(trzy_wydawnictwa_ciagle):
    """Brak wybranej wartości filtra → queryset niezmieniony."""
    qs = _apply(None, Wydawnictwo_Ciagle)
    assert qs.count() == 3


def test_lookups_ma_trzy_opcje():
    f = PBNStatusFilter(None, {}, Wydawnictwo_Ciagle, None)
    keys = [k for k, _label in f.lookups(None, None)]
    assert keys == ["deleted", "active", "brak"]


@pytest.mark.django_db
def test_filtr_dziala_tez_dla_zwarte():
    wz_del = baker.make(Wydawnictwo_Zwarte, pbn_uid=_pub("wz_del", "DELETED"))
    wz_act = baker.make(Wydawnictwo_Zwarte, pbn_uid=_pub("wz_act", "ACTIVE"))
    qs = _apply("deleted", Wydawnictwo_Zwarte)
    assert wz_del in qs
    assert wz_act not in qs


def test_filtr_podpiety_do_obu_adminow():
    """Regresja: filtr jest w list_filter obu adminów."""
    from bpp.admin.wydawnictwo_ciagle import Wydawnictwo_CiagleAdmin
    from bpp.admin.wydawnictwo_zwarte import Wydawnictwo_ZwarteAdmin

    assert PBNStatusFilter in Wydawnictwo_CiagleAdmin.list_filter
    assert PBNStatusFilter in Wydawnictwo_ZwarteAdmin.list_filter


@pytest.mark.django_db
def test_djangoql_pbn_uid_status_dziala(trzy_wydawnictwa_ciagle):
    """Regresja: DjangoQL admina waliduje i filtruje ``pbn_uid.status``.

    ``pbn_api`` nie jest wykluczone z ``BppQLSchema``, więc traversal
    ``pbn_uid.status`` musi się walidować i faktycznie zawężać wyniki. To pilnuje,
    że przyszłe uszczelnianie schematu nie odetnie tej (użytecznej) ścieżki.
    """
    from djangoql.queryset import apply_search

    from bpp.djangoql_schema import BppQLSchema

    wc_del, wc_act, wc_brak = trzy_wydawnictwa_ciagle

    qs = apply_search(
        Wydawnictwo_Ciagle.objects.all(),
        'pbn_uid.status = "DELETED"',
        schema=BppQLSchema,
    )

    assert wc_del in qs
    assert wc_act not in qs
    assert wc_brak not in qs

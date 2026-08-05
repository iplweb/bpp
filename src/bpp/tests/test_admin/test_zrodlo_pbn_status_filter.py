"""Filtry admina po statusie ŹRÓDŁA w PBN.

Dwa uzupełnienia do ``PBNStatusFilter`` (który patrzy tylko na własny
``pbn_uid`` rekordu):

1. ``ZrodloUsunieteWPBNFilter`` — w adminie ``Wydawnictwo_Ciagle`` wyłapuje
   prace, których ŹRÓDŁO (czasopismo) jest skasowane w PBN
   (``zrodlo.pbn_uid.status == "DELETED"``), niezależnie od statusu samego
   rekordu.
2. ``PBNStatusFilter`` podpięty do adminu ``Zrodlo`` — źródło samo w sobie ma
   ``pbn_uid`` (Journal) ze statusem, więc ten sam filtr działa 1:1.
"""

import pytest
from model_bakery import baker

from bpp.admin.filters import PBNStatusFilter, ZrodloUsunieteWPBNFilter
from bpp.models import Wydawnictwo_Ciagle, Zrodlo
from pbn_api.models import Journal


def _journal(mongo_id, status):
    return baker.make(
        Journal,
        mongoId=mongo_id,
        versions=[{"current": True, "object": {"title": mongo_id}}],
        status=status,
    )


def _apply(filter_cls, value, model, queryset=None):
    f = filter_cls(None, {}, model, None)
    f.value = lambda *a, **k: value
    return f.queryset(None, queryset if queryset is not None else model.objects.all())


# --- Wydawnictwo_Ciagle po statusie ŹRÓDŁA -------------------------------


@pytest.fixture
def trzy_ciagle_wg_zrodla():
    """(deleted, active, brak) — Wydawnictwo_Ciagle wg statusu PBN źródła."""
    z_del = baker.make(Zrodlo, pbn_uid=_journal("z_del", "DELETED"))
    z_act = baker.make(Zrodlo, pbn_uid=_journal("z_act", "ACTIVE"))
    wc_del = baker.make(Wydawnictwo_Ciagle, zrodlo=z_del)
    wc_act = baker.make(Wydawnictwo_Ciagle, zrodlo=z_act)
    wc_brak = baker.make(Wydawnictwo_Ciagle, zrodlo=None)
    return wc_del, wc_act, wc_brak


@pytest.mark.django_db
def test_zrodlo_deleted(trzy_ciagle_wg_zrodla):
    wc_del, wc_act, wc_brak = trzy_ciagle_wg_zrodla
    qs = _apply(ZrodloUsunieteWPBNFilter, "deleted", Wydawnictwo_Ciagle)
    assert wc_del in qs
    assert wc_act not in qs
    assert wc_brak not in qs


@pytest.mark.django_db
def test_zrodlo_active(trzy_ciagle_wg_zrodla):
    wc_del, wc_act, wc_brak = trzy_ciagle_wg_zrodla
    qs = _apply(ZrodloUsunieteWPBNFilter, "active", Wydawnictwo_Ciagle)
    assert wc_act in qs
    assert wc_del not in qs
    assert wc_brak not in qs


@pytest.mark.django_db
def test_zrodlo_brak(trzy_ciagle_wg_zrodla):
    """'brak' — źródło bez powiązania PBN (albo w ogóle bez źródła)."""
    wc_del, wc_act, wc_brak = trzy_ciagle_wg_zrodla
    z_bez_pbn = baker.make(Zrodlo, pbn_uid=None)
    wc_zrodlo_bez_pbn = baker.make(Wydawnictwo_Ciagle, zrodlo=z_bez_pbn)
    qs = _apply(ZrodloUsunieteWPBNFilter, "brak", Wydawnictwo_Ciagle)
    assert wc_brak in qs
    assert wc_zrodlo_bez_pbn in qs
    assert wc_del not in qs
    assert wc_act not in qs


@pytest.mark.django_db
def test_zrodlo_brak_wartosci_nie_zaweza(trzy_ciagle_wg_zrodla):
    qs = _apply(ZrodloUsunieteWPBNFilter, None, Wydawnictwo_Ciagle)
    assert qs.count() == 3


def test_zrodlo_lookups_ma_trzy_opcje():
    f = ZrodloUsunieteWPBNFilter(None, {}, Wydawnictwo_Ciagle, None)
    keys = [k for k, _label in f.lookups(None, None)]
    assert keys == ["deleted", "active", "brak"]


# --- Zrodlo po własnym statusie PBN --------------------------------------


@pytest.mark.django_db
def test_pbnstatusfilter_dziala_dla_zrodla():
    z_del = baker.make(Zrodlo, pbn_uid=_journal("zz_del", "DELETED"))
    z_act = baker.make(Zrodlo, pbn_uid=_journal("zz_act", "ACTIVE"))
    z_brak = baker.make(Zrodlo, pbn_uid=None)

    qs_del = _apply(PBNStatusFilter, "deleted", Zrodlo)
    assert z_del in qs_del
    assert z_act not in qs_del
    assert z_brak not in qs_del

    qs_brak = _apply(PBNStatusFilter, "brak", Zrodlo)
    assert z_brak in qs_brak
    assert z_del not in qs_brak


# --- Podpięcie do adminów (regresja) -------------------------------------


def test_filtry_podpiete_do_adminow():
    from bpp.admin.wydawnictwo_ciagle import Wydawnictwo_CiagleAdmin
    from bpp.admin.zrodlo import ZrodloAdmin

    assert ZrodloUsunieteWPBNFilter in Wydawnictwo_CiagleAdmin.list_filter
    assert PBNStatusFilter in ZrodloAdmin.list_filter

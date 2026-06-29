from decimal import Decimal

import pytest
from model_bakery import baker

from rozbieznosci.core import get_base_queryset_for_metryka, ustaw_ze_zrodla
from rozbieznosci.metryki import METRYKI_BY_SLUG
from rozbieznosci.models import IgnorowanaRozbieznosc, RozbieznoscLog


def praca_field(field):
    return field


def _wc_ze_zrodlem(rok, praca_val, zrodlo_val, field):
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Punktacja_Zrodla", zrodlo=zrodlo, rok=rok, **{field: zrodlo_val})
    return baker.make(
        "bpp.Wydawnictwo_Ciagle",
        zrodlo=zrodlo,
        rok=rok,
        **{praca_field(field): praca_val},
    )


@pytest.mark.django_db
def test_if_rozbieznosc_wykrywana():
    m = METRYKI_BY_SLUG["if"]
    wc = _wc_ze_zrodlem(
        2023, praca_val="1.500", zrodlo_val="2.500", field="impact_factor"
    )
    qs = get_base_queryset_for_metryka(m)
    assert wc in list(qs)


@pytest.mark.django_db
def test_if_zero_zrodla_domyslnie_ukryte():
    m = METRYKI_BY_SLUG["if"]
    wc = _wc_ze_zrodlem(
        2023, praca_val="1.500", zrodlo_val="0.000", field="impact_factor"
    )
    # domyślnie (pokaz_puste_zrodla=False) rekord ze źródłem 0 jest ukryty
    assert wc not in list(get_base_queryset_for_metryka(m))
    # po odsłonięciu — widoczny
    assert wc in list(get_base_queryset_for_metryka(m, pokaz_puste_zrodla=True))


@pytest.mark.django_db
def test_kwartyl_null_zrodla_domyslnie_ukryty():
    m = METRYKI_BY_SLUG["kw_scopus"]
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Punktacja_Zrodla", zrodlo=zrodlo, rok=2023, kwartyl_w_scopus=None)
    wc = baker.make(
        "bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=2023, kwartyl_w_scopus=2
    )
    assert wc not in list(get_base_queryset_for_metryka(m))
    assert wc in list(get_base_queryset_for_metryka(m, pokaz_puste_zrodla=True))


@pytest.mark.django_db
def test_ignorowane_wykluczone_per_metryka():
    m = METRYKI_BY_SLUG["if"]

    # Rekord zignorowany — nie powinien się pojawić
    wc_ign = _wc_ze_zrodlem(
        2023, praca_val="1.500", zrodlo_val="2.500", field="impact_factor"
    )
    IgnorowanaRozbieznosc.objects.create(metryka="if", rekord=wc_ign)
    assert wc_ign not in list(get_base_queryset_for_metryka(m))

    # Inny rekord bez ignoru w tej samej metryce — powinien się pojawić
    wc_inny = _wc_ze_zrodlem(
        2023, praca_val="1.500", zrodlo_val="2.500", field="impact_factor"
    )
    assert wc_inny in list(get_base_queryset_for_metryka(m))


@pytest.mark.django_db
def test_ustaw_ze_zrodla_aktualizuje_i_loguje():
    m = METRYKI_BY_SLUG["if"]
    wc = _wc_ze_zrodlem(
        2023, praca_val="1.500", zrodlo_val="2.500", field="impact_factor"
    )
    updated, errors = ustaw_ze_zrodla([wc.pk], m)
    assert (updated, errors) == (1, 0)
    wc.refresh_from_db()
    assert str(wc.impact_factor) == "2.500"
    assert RozbieznoscLog.objects.filter(metryka="if", rekord=wc).count() == 1


@pytest.mark.django_db
def test_ustaw_mnisw_wola_przelicz(monkeypatch):
    m = METRYKI_BY_SLUG["mnisw"]
    # Decimal wymagany — baker.make przechowuje wartość as-is w pamięci;
    # przelicz_punkty_dyscyplin() porównuje punkty_kbn z int i pada na str.
    wc = _wc_ze_zrodlem(
        2023,
        praca_val=Decimal("10.00"),
        zrodlo_val=Decimal("40.00"),
        field="punkty_kbn",
    )
    called = {"n": 0}
    from bpp.models import Wydawnictwo_Ciagle

    monkeypatch.setattr(
        Wydawnictwo_Ciagle,
        "przelicz_punkty_dyscyplin",
        lambda self: called.__setitem__("n", called["n"] + 1),
    )
    ustaw_ze_zrodla([wc.pk], m)
    # @denormalized cached_punkty_dyscyplin.pre_save() wywołuje przelicz raz
    # (przy wc.save()); ustaw_ze_zrodla wywołuje je raz więcej jawnie
    # (recalculates_disciplines=True). Razem: 2.
    assert called["n"] == 2

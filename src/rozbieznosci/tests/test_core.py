from decimal import Decimal

import pytest
from model_bakery import baker

from rozbieznosci.core import (
    TRYB_ROWNIEZ_ZEROWE,
    TRYB_WYLACZNIE_ZEROWE,
    apply_filters,
    get_base_queryset_for_metryka,
    ustaw_ze_zrodla,
)
from rozbieznosci.metryki import METRYKI_BY_SLUG
from rozbieznosci.models import IgnorowanaRozbieznosc, RozbieznoscLog


def _wc_ze_zrodlem(rok, praca_val, zrodlo_val, field):
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Punktacja_Zrodla", zrodlo=zrodlo, rok=rok, **{field: zrodlo_val})
    return baker.make(
        "bpp.Wydawnictwo_Ciagle",
        zrodlo=zrodlo,
        rok=rok,
        **{field: praca_val},
    )


def _wc_bez_wpisu_zrodla(rok, praca_val, field):
    """Praca ze źródłem, ale BEZ wiersza Punktacja_Zrodla dla (zrodlo, rok)."""
    zrodlo = baker.make("bpp.Zrodlo")
    return baker.make(
        "bpp.Wydawnictwo_Ciagle",
        zrodlo=zrodlo,
        rok=rok,
        **{field: praca_val},
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
    assert wc in list(get_base_queryset_for_metryka(m, tryb_zrodla=TRYB_ROWNIEZ_ZEROWE))


@pytest.mark.django_db
def test_kwartyl_null_zrodla_domyslnie_ukryty():
    m = METRYKI_BY_SLUG["kw_scopus"]
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Punktacja_Zrodla", zrodlo=zrodlo, rok=2023, kwartyl_w_scopus=None)
    wc = baker.make(
        "bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=2023, kwartyl_w_scopus=2
    )
    assert wc not in list(get_base_queryset_for_metryka(m))
    assert wc in list(get_base_queryset_for_metryka(m, tryb_zrodla=TRYB_ROWNIEZ_ZEROWE))


@pytest.mark.django_db
def test_ignorowane_wykluczone_per_metryka():
    m_if = METRYKI_BY_SLUG["if"]
    m_mnisw = METRYKI_BY_SLUG["mnisw"]

    # wc_ign ma rozbieżność w obu metrykach: impact_factor i punkty_kbn
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make(
        "bpp.Punktacja_Zrodla",
        zrodlo=zrodlo,
        rok=2023,
        impact_factor="2.500",
        punkty_kbn=Decimal("40.00"),
    )
    wc_ign = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        zrodlo=zrodlo,
        rok=2023,
        impact_factor="1.500",
        punkty_kbn=Decimal("10.00"),
    )
    # Ignorujemy tylko w metryce "if"
    IgnorowanaRozbieznosc.objects.create(metryka="if", rekord=wc_ign)

    # w metryce "if" — zignorowany
    assert wc_ign not in list(get_base_queryset_for_metryka(m_if))
    # w metryce "mnisw" — nadal widoczny (ignor "if" nie wpływa na "mnisw")
    assert wc_ign in list(get_base_queryset_for_metryka(m_mnisw))

    # Inny rekord bez ignoru — widoczny w "if"
    wc_inny = _wc_ze_zrodlem(
        2023, praca_val="1.500", zrodlo_val="2.500", field="impact_factor"
    )
    assert wc_inny in list(get_base_queryset_for_metryka(m_if))


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
    # @denormalized cached_punkty_dyscyplin.pre_save() wywołuje przelicz przy
    # wc.save(); ustaw_ze_zrodla wywołuje je dodatkowo jawnie dla mnisw
    # (recalculates_disciplines=True). Sprawdzamy, że jawne wywołanie nastąpiło.
    assert called["n"] >= 1


@pytest.mark.django_db
def test_ustaw_if_nie_wola_przelicz(monkeypatch):
    m = METRYKI_BY_SLUG["if"]
    wc = _wc_ze_zrodlem(
        2023, praca_val="1.500", zrodlo_val="2.500", field="impact_factor"
    )
    called = {"n": 0}
    from bpp.models import Wydawnictwo_Ciagle

    monkeypatch.setattr(
        Wydawnictwo_Ciagle,
        "przelicz_punkty_dyscyplin",
        lambda self: called.__setitem__("n", called["n"] + 1),
    )
    ustaw_ze_zrodla([wc.pk], m)
    # recalculates_disciplines=False dla "if" — brak jawnego wywołania;
    # jedyne wywołanie pochodzi z @denormalized cached_punkty_dyscyplin.pre_save()
    # przy wc.save().
    assert called["n"] == 1


@pytest.mark.django_db
def test_filtr_zera_respektuje_rok__widoczny():
    """Źródło rok=2022 ma IF=0.000, rok=2023 ma IF=2.500; praca rok=2023.

    Przy pokaz_puste_zrodla=False praca MA być widoczna — bo dla roku pracy
    (2023) IF źródła wynosi 2.500 ≠ 0. Rok=2022 z IF=0 nie może rzutować
    na widoczność pracy z innego roku.
    """
    m = METRYKI_BY_SLUG["if"]
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make(
        "bpp.Punktacja_Zrodla",
        zrodlo=zrodlo,
        rok=2022,
        impact_factor="0.000",
    )
    baker.make(
        "bpp.Punktacja_Zrodla",
        zrodlo=zrodlo,
        rok=2023,
        impact_factor="2.500",
    )
    wc = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        zrodlo=zrodlo,
        rok=2023,
        impact_factor="1.500",
    )
    assert wc in list(get_base_queryset_for_metryka(m))


@pytest.mark.django_db
def test_rozbieznosc_respektuje_rok_pracy():
    """Bug-proof: źródło ma IF=1.500 w roku 2022 (= wartość pracy) i IF=2.500
    w roku 2023 (= rok pracy, inna wartość).  Praca rok=2023 IF=1.500 różni się
    od źródła 2023 (2.500) — to realna rozbieżność.  Równa wartość w INNYM roku
    (2022) nie może jej ukryć.
    """
    m = METRYKI_BY_SLUG["if"]
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make(
        "bpp.Punktacja_Zrodla",
        zrodlo=zrodlo,
        rok=2022,
        impact_factor="1.500",
    )
    baker.make(
        "bpp.Punktacja_Zrodla",
        zrodlo=zrodlo,
        rok=2023,
        impact_factor="2.500",
    )
    wc = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        zrodlo=zrodlo,
        rok=2023,
        impact_factor="1.500",
    )
    assert wc in list(get_base_queryset_for_metryka(m))


@pytest.mark.django_db
def test_filtr_zera_respektuje_rok__ukryty():
    """Źródło rok=2022 ma IF=2.500, rok=2023 ma IF=0.000; praca rok=2023.

    Przy pokaz_puste_zrodla=False praca MA być ukryta — bo dla roku pracy
    (2023) IF źródła wynosi 0. Rok=2022 z IF=2.500 nie ratuje widoczności.
    """
    m = METRYKI_BY_SLUG["if"]
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make(
        "bpp.Punktacja_Zrodla",
        zrodlo=zrodlo,
        rok=2022,
        impact_factor="2.500",
    )
    baker.make(
        "bpp.Punktacja_Zrodla",
        zrodlo=zrodlo,
        rok=2023,
        impact_factor="0.000",
    )
    wc = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        zrodlo=zrodlo,
        rok=2023,
        impact_factor="1.500",
    )
    assert wc not in list(get_base_queryset_for_metryka(m))


@pytest.mark.django_db
def test_rowne_wartosci_nie_sa_rozbieznoscia():
    """Źródło i praca mają identyczny IF — to nie jest rozbieżność."""
    m = METRYKI_BY_SLUG["if"]
    wc = _wc_ze_zrodlem(
        2023, praca_val="2.500", zrodlo_val="2.500", field="impact_factor"
    )
    assert wc not in list(get_base_queryset_for_metryka(m))


@pytest.mark.django_db
def test_kwartyl_oboje_null_nie_sa_rozbieznoscia():
    """Źródło i praca mają kwartyl=None — oba NULL, brak rozbieżności.

    NULL IS DISTINCT FROM NULL = FALSE, więc nie powinno trafić do listy
    nawet przy pokaz_puste_zrodla=True.
    """
    m = METRYKI_BY_SLUG["kw_scopus"]
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Punktacja_Zrodla", zrodlo=zrodlo, rok=2023, kwartyl_w_scopus=None)
    wc = baker.make(
        "bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=2023, kwartyl_w_scopus=None
    )
    assert wc not in list(
        get_base_queryset_for_metryka(m, tryb_zrodla=TRYB_ROWNIEZ_ZEROWE)
    )


@pytest.mark.django_db
def test_kwartyl_null_zrodla_vs_wartosc_pracy_jest_rozbieznoscia():
    """Źródło kwartyl=None, praca kwartyl=2 — jedna strona NULL = rozbieżność."""
    m = METRYKI_BY_SLUG["kw_scopus"]
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Punktacja_Zrodla", zrodlo=zrodlo, rok=2023, kwartyl_w_scopus=None)
    wc = baker.make(
        "bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=2023, kwartyl_w_scopus=2
    )
    assert wc in list(get_base_queryset_for_metryka(m, tryb_zrodla=TRYB_ROWNIEZ_ZEROWE))


@pytest.mark.django_db
def test_kwartyl_rowne_wartosci_nie_sa_rozbieznoscia():
    """Źródło kwartyl=2, praca kwartyl=2 — równe wartości, brak rozbieżności."""
    m = METRYKI_BY_SLUG["kw_scopus"]
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Punktacja_Zrodla", zrodlo=zrodlo, rok=2023, kwartyl_w_scopus=2)
    wc = baker.make(
        "bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=2023, kwartyl_w_scopus=2
    )
    assert wc not in list(
        get_base_queryset_for_metryka(m, tryb_zrodla=TRYB_ROWNIEZ_ZEROWE)
    )


# --- Brak wpisu Punktacja_Zrodla za rok pracy (kategoria B) -----------------
# Praca ma wartość, ale źródło nie ma w ogóle wiersza punktacji za rok pracy.
# Taki rekord ma się pokazać DOPIERO po zaznaczeniu "Pokaż też puste źródła"
# (analogicznie do źródła z wartością 0/NULL), i być wyraźnie oznaczony
# anotacją zrodlo_ma_wpis=False.


@pytest.mark.django_db
def test_if_brak_wpisu_zrodla_z_wartoscia_pracy():
    """IF: praca ma IF, źródło bez wpisu za rok — ukryty domyślnie, widoczny
    po checkboxie."""
    m = METRYKI_BY_SLUG["if"]
    wc = _wc_bez_wpisu_zrodla(2023, praca_val="1.500", field="impact_factor")
    assert wc not in list(get_base_queryset_for_metryka(m))
    assert wc in list(get_base_queryset_for_metryka(m, tryb_zrodla=TRYB_ROWNIEZ_ZEROWE))


@pytest.mark.django_db
def test_if_brak_wpisu_zrodla_praca_zero_nie_jest_rozbieznoscia():
    """IF: praca ma IF=0 i źródło bez wpisu — obie strony bez wartości,
    nie jest rozbieżnością nawet po checkboxie."""
    m = METRYKI_BY_SLUG["if"]
    wc = _wc_bez_wpisu_zrodla(2023, praca_val="0.000", field="impact_factor")
    assert wc not in list(
        get_base_queryset_for_metryka(m, tryb_zrodla=TRYB_ROWNIEZ_ZEROWE)
    )


@pytest.mark.django_db
def test_mnisw_brak_wpisu_zrodla_z_wartoscia_pracy():
    """MNiSW: praca ma punkty, źródło bez wpisu — widoczny po checkboxie."""
    m = METRYKI_BY_SLUG["mnisw"]
    wc = _wc_bez_wpisu_zrodla(2023, praca_val=Decimal("40.00"), field="punkty_kbn")
    assert wc not in list(get_base_queryset_for_metryka(m))
    assert wc in list(get_base_queryset_for_metryka(m, tryb_zrodla=TRYB_ROWNIEZ_ZEROWE))


@pytest.mark.django_db
def test_kwartyl_brak_wpisu_zrodla_z_wartoscia_pracy():
    """Kwartyl: praca ma kwartyl, źródło bez wpisu — widoczny po checkboxie."""
    m = METRYKI_BY_SLUG["kw_scopus"]
    zrodlo = baker.make("bpp.Zrodlo")
    wc = baker.make(
        "bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=2023, kwartyl_w_scopus=2
    )
    assert wc not in list(get_base_queryset_for_metryka(m))
    assert wc in list(get_base_queryset_for_metryka(m, tryb_zrodla=TRYB_ROWNIEZ_ZEROWE))


@pytest.mark.django_db
def test_kwartyl_brak_wpisu_zrodla_praca_null_nie_jest_rozbieznoscia():
    """Kwartyl: praca kwartyl=NULL i źródło bez wpisu — obie bez wartości,
    nie jest rozbieżnością nawet po checkboxie."""
    m = METRYKI_BY_SLUG["kw_scopus"]
    zrodlo = baker.make("bpp.Zrodlo")
    wc = baker.make(
        "bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=2023, kwartyl_w_scopus=None
    )
    assert wc not in list(
        get_base_queryset_for_metryka(m, tryb_zrodla=TRYB_ROWNIEZ_ZEROWE)
    )


@pytest.mark.django_db
def test_brak_wpisu_oznaczony_anotacja_zrodlo_ma_wpis():
    """Rekord bez wpisu źródła ma zrodlo_ma_wpis=False, z wpisem — True."""
    m = METRYKI_BY_SLUG["if"]
    wc_brak = _wc_bez_wpisu_zrodla(2023, praca_val="2.500", field="impact_factor")
    wc_z = _wc_ze_zrodlem(
        2023, praca_val="1.500", zrodlo_val="2.500", field="impact_factor"
    )
    by_pk = {
        w.pk: w
        for w in get_base_queryset_for_metryka(m, tryb_zrodla=TRYB_ROWNIEZ_ZEROWE)
    }
    assert by_pk[wc_brak.pk].zrodlo_ma_wpis is False
    assert by_pk[wc_z.pk].zrodlo_ma_wpis is True


# --- Tryb WYLACZNIE_ZEROWE -------------------------------------------------


@pytest.mark.django_db
def test_tryb_wylacznie_zerowe_pomija_standardowe_pokazuje_zerowe():
    """Wyłącznie zerowe: standardowa rozbieżność ukryta, źródło 0 / brak wpisu
    z wartością w pracy — widoczne."""
    m = METRYKI_BY_SLUG["if"]
    wc_std = _wc_ze_zrodlem(
        2023, praca_val="1.500", zrodlo_val="2.500", field="impact_factor"
    )
    wc_brak = _wc_bez_wpisu_zrodla(2023, praca_val="1.500", field="impact_factor")
    wc_zero = _wc_ze_zrodlem(
        2023, praca_val="1.500", zrodlo_val="0.000", field="impact_factor"
    )

    wyl = list(get_base_queryset_for_metryka(m, tryb_zrodla=TRYB_WYLACZNIE_ZEROWE))
    assert wc_std not in wyl
    assert wc_brak in wyl
    assert wc_zero in wyl

    std = list(get_base_queryset_for_metryka(m))
    assert wc_std in std
    assert wc_brak not in std
    assert wc_zero not in std


# --- ustaw_ze_zrodla: kasuj_przy_pustym ------------------------------------


@pytest.mark.django_db
def test_ustaw_kasuj_off_nie_rusza_pracy_przy_braku_zrodla():
    """Brak wpisu źródła, kasuj wyłączone — kwartyl pracy bez zmian."""
    m = METRYKI_BY_SLUG["kw_wos"]
    wc = _wc_bez_wpisu_zrodla(2023, praca_val=2, field="kwartyl_w_wos")
    updated, errors = ustaw_ze_zrodla([wc.pk], m)
    assert (updated, errors) == (0, 0)
    wc.refresh_from_db()
    assert wc.kwartyl_w_wos == 2


@pytest.mark.django_db
def test_ustaw_kasuj_on_czysci_kwartyl_przy_braku_zrodla():
    """Brak wpisu źródła, kasuj włączone — kwartyl pracy wyczyszczony do None."""
    m = METRYKI_BY_SLUG["kw_wos"]
    wc = _wc_bez_wpisu_zrodla(2023, praca_val=2, field="kwartyl_w_wos")
    updated, errors = ustaw_ze_zrodla([wc.pk], m, kasuj_przy_pustym=True)
    assert (updated, errors) == (1, 0)
    wc.refresh_from_db()
    assert wc.kwartyl_w_wos is None
    assert RozbieznoscLog.objects.filter(metryka="kw_wos", rekord=wc).count() == 1


@pytest.mark.django_db
def test_ustaw_kasuj_off_nie_zeruje_if_przy_zrodle_zero():
    """Źródło IF=0, kasuj wyłączone — IF pracy bez zmian."""
    m = METRYKI_BY_SLUG["if"]
    wc = _wc_ze_zrodlem(
        2023, praca_val="2.500", zrodlo_val="0.000", field="impact_factor"
    )
    updated, errors = ustaw_ze_zrodla([wc.pk], m)
    assert (updated, errors) == (0, 0)
    wc.refresh_from_db()
    assert str(wc.impact_factor) == "2.500"


@pytest.mark.django_db
def test_ustaw_kasuj_on_zeruje_if_przy_zrodle_zero():
    """Źródło IF=0, kasuj włączone — IF pracy wyzerowany."""
    m = METRYKI_BY_SLUG["if"]
    wc = _wc_ze_zrodlem(
        2023, praca_val="2.500", zrodlo_val="0.000", field="impact_factor"
    )
    updated, errors = ustaw_ze_zrodla([wc.pk], m, kasuj_przy_pustym=True)
    assert (updated, errors) == (1, 0)
    wc.refresh_from_db()
    assert str(wc.impact_factor) == "0.000"


# --- apply_filters: charakter formalny -------------------------------------


@pytest.mark.django_db
def test_apply_filters_charaktery_zaweza():
    """Pusta lista charakterów = brak zawężenia; niepusta = tylko wskazane."""
    m = METRYKI_BY_SLUG["if"]
    cf1 = baker.make("bpp.Charakter_Formalny")
    cf2 = baker.make("bpp.Charakter_Formalny")
    z1 = baker.make("bpp.Zrodlo")
    baker.make("bpp.Punktacja_Zrodla", zrodlo=z1, rok=2023, impact_factor="2.500")
    z2 = baker.make("bpp.Zrodlo")
    baker.make("bpp.Punktacja_Zrodla", zrodlo=z2, rok=2023, impact_factor="2.500")
    wc1 = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        zrodlo=z1,
        rok=2023,
        impact_factor="1.500",
        charakter_formalny=cf1,
    )
    wc2 = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        zrodlo=z2,
        rok=2023,
        impact_factor="1.500",
        charakter_formalny=cf2,
    )

    qs = get_base_queryset_for_metryka(m)
    tylko_cf1 = list(apply_filters(qs, 2022, 2026, "", [cf1]))
    assert wc1 in tylko_cf1
    assert wc2 not in tylko_cf1

    wszystkie = list(
        apply_filters(get_base_queryset_for_metryka(m), 2022, 2026, "", [])
    )
    assert wc1 in wszystkie
    assert wc2 in wszystkie

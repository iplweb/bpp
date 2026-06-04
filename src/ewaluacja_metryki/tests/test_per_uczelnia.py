from decimal import Decimal

import pytest
from model_bakery import baker

from ewaluacja_metryki.models import MetrykaAutora, StatusGenerowania


def _make_metryka(autor, dyscyplina, uczelnia, **kw):
    defaults = dict(
        slot_maksymalny=Decimal("4.0"),
        slot_nazbierany=Decimal("2.0"),
        punkty_nazbierane=Decimal("100.0"),
        slot_wszystkie=Decimal("3.0"),
        punkty_wszystkie=Decimal("150.0"),
    )
    defaults.update(kw)
    return MetrykaAutora.objects.create(
        autor=autor, dyscyplina_naukowa=dyscyplina, uczelnia=uczelnia, **defaults
    )


@pytest.mark.django_db
def test_metryka_ma_uczelnia(autor_jan_kowalski, dyscyplina1):
    u = baker.make("bpp.Uczelnia")
    m = _make_metryka(autor_jan_kowalski, dyscyplina1, u)
    assert m.uczelnia_id == u.pk


@pytest.mark.django_db
def test_metryka_unique_together_z_uczelnia(autor_jan_kowalski, dyscyplina1):
    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    # ta sama (autor, dyscyplina), różne uczelnie → OK (rozłączne metryki)
    _make_metryka(autor_jan_kowalski, dyscyplina1, u1)
    _make_metryka(autor_jan_kowalski, dyscyplina1, u2)
    assert MetrykaAutora.objects.count() == 2


@pytest.mark.django_db
def test_status_generowania_per_uczelnia():
    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    s1 = StatusGenerowania.get_or_create(uczelnia=u1)
    s2 = StatusGenerowania.get_or_create(uczelnia=u2)
    assert s1.pk != s2.pk
    assert s1.uczelnia_id == u1.pk
    assert s2.uczelnia_id == u2.pk


@pytest.mark.django_db
def test_oblicz_metryki_dla_autora_nie_sumuje_slotow_z_innej_uczelni(
    autor_jan_kowalski, dyscyplina1
):
    """Regresja R2: slot_maksymalny nie może sumować udziałów wszystkich uczelni."""
    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc
    from ewaluacja_metryki.utils import oblicz_metryki_dla_autora

    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    IloscUdzialowDlaAutoraZaCalosc.objects.create(
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora=None,
        ilosc_udzialow=Decimal("4.0"),
        ilosc_udzialow_monografie=Decimal("0"),
        uczelnia=u1,
    )
    IloscUdzialowDlaAutoraZaCalosc.objects.create(
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora=None,
        ilosc_udzialow=Decimal("9.0"),
        ilosc_udzialow_monografie=Decimal("0"),
        uczelnia=u2,
    )
    metryka, _ = oblicz_metryki_dla_autora(
        autor=autor_jan_kowalski, dyscyplina=dyscyplina1, uczelnia=u1
    )
    # slot_maksymalny = 4.0 (tylko u1), NIE 13.0 (suma u1+u2)
    assert metryka.slot_maksymalny == Decimal("4.0")
    assert metryka.uczelnia_id == u1.pk


@pytest.mark.django_db
def test_generuj_metryki_task_scope_per_uczelnia(autor_jan_kowalski, dyscyplina1):
    """Task generuje metryki tylko dla swojej uczelni, nie wyciera innej."""
    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc
    from ewaluacja_metryki.tasks import generuj_metryki_task

    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    # istniejąca metryka u2 — nie wolno jej skasować
    _make_metryka(autor_jan_kowalski, dyscyplina1, u2)
    IloscUdzialowDlaAutoraZaCalosc.objects.create(
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora=None,
        ilosc_udzialow=Decimal("4.0"),
        ilosc_udzialow_monografie=Decimal("0"),
        uczelnia=u1,
    )
    generuj_metryki_task(
        uczelnia_id=u1.pk, przelicz_liczbe_n=False, rodzaje_autora=[" "]
    )
    # metryka u2 nadal istnieje (scoped delete nie wyciera obcej uczelni)
    assert MetrykaAutora.objects.filter(uczelnia=u2).exists()

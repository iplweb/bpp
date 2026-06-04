from decimal import Decimal

import pytest
from model_bakery import baker

from ewaluacja_metryki.models import MetrykaAutora


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

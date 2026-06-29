from decimal import Decimal

import pytest
from django.urls import reverse
from model_bakery import baker

from rozbieznosci.tasks import task_ustaw_ze_zrodla


def _rozbiezny(field, praca, zrodlo_val, rok=2023):
    """Create a Wydawnictwo_Ciagle with a discrepancy vs its source's score."""
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make(
        "bpp.Punktacja_Zrodla",
        zrodlo=zrodlo,
        rok=rok,
        **{field: Decimal(zrodlo_val)},
    )
    return baker.make(
        "bpp.Wydawnictwo_Ciagle",
        zrodlo=zrodlo,
        rok=rok,
        **{field: Decimal(praca)},
    )


@pytest.mark.django_db
def test_bulk_sync_maly_batch(client_with_group):
    wc = _rozbiezny("impact_factor", "1.000", "2.000")
    url = reverse("rozbieznosci:ustaw_wszystkie", kwargs={"metryka": "if"})
    # POST z filtrami => synchronicznie (1 < 20)
    resp = client_with_group.post(url, {"rok_od": 2022, "rok_do": 2026})
    assert resp.status_code in (301, 302)
    wc.refresh_from_db()
    assert str(wc.impact_factor) == "2.000"


@pytest.mark.django_db
def test_task_aktualizuje():
    wc = _rozbiezny("impact_factor", "1.000", "2.000")
    # bind=True — use .apply() to inject the Celery task context (self)
    result = task_ustaw_ze_zrodla.apply(args=([wc.pk], "if")).result
    assert result["updated"] == 1
    wc.refresh_from_db()
    assert str(wc.impact_factor) == "2.000"


@pytest.mark.django_db
def test_confirm_get_pokazuje_liczbe(client_with_group):
    _rozbiezny("punkty_kbn", "10.00", "40.00")
    url = reverse("rozbieznosci:ustaw_wszystkie", kwargs={"metryka": "mnisw"})
    resp = client_with_group.get(f"{url}?rok_od=2022&rok_do=2026")
    assert resp.status_code == 200
    assert resp.context["count"] == 1

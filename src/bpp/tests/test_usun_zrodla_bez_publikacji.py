"""Testy komendy `usun_zrodla_bez_publikacji` (masowe kasowanie pustych źródeł)."""

import pytest
from django.core.management import call_command
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from bpp.models.zrodlo import Zrodlo
from pbn_api.models import Journal


@pytest.mark.django_db
def test_usun_zrodla_bez_publikacji_kasuje_puste_zostawia_z_publikacjami():
    pusty = baker.make(Zrodlo)  # bez publikacji, bez mniswID
    pusty_z_mnisw = baker.make(Zrodlo, pbn_uid=baker.make(Journal, mniswId=5))
    z_publikacja = baker.make(Zrodlo)
    baker.make(Wydawnictwo_Ciagle, zrodlo=z_publikacja)

    call_command("usun_zrodla_bez_publikacji")

    assert not Zrodlo.objects.filter(pk=pusty.pk).exists()
    assert not Zrodlo.objects.filter(pk=pusty_z_mnisw.pk).exists()
    assert Zrodlo.objects.filter(pk=z_publikacja.pk).exists()


@pytest.mark.django_db
def test_usun_zrodla_bez_publikacji_bez_mnisw_zostawia_ministerialne():
    pusty = baker.make(Zrodlo)  # bez mniswID → do usunięcia
    pusty_z_mnisw = baker.make(Zrodlo, pbn_uid=baker.make(Journal, mniswId=5))

    call_command("usun_zrodla_bez_publikacji", "--bez-mnisw")

    assert not Zrodlo.objects.filter(pk=pusty.pk).exists()
    assert Zrodlo.objects.filter(pk=pusty_z_mnisw.pk).exists()  # ma mniswID → zostaje


@pytest.mark.django_db
def test_usun_zrodla_bez_publikacji_dry_run_nic_nie_kasuje():
    pusty = baker.make(Zrodlo)

    call_command("usun_zrodla_bez_publikacji", "--dry-run")

    assert Zrodlo.objects.filter(pk=pusty.pk).exists()


@pytest.mark.django_db
def test_admin_action_usun_bez_publikacji_select_across(admin_client):
    """Akcja admina z select_across (zaznacz wszystkie pasujące) kasuje puste
    źródła bez wysyłania tysięcy pól POST; źródła z publikacjami zostają."""
    pusty1 = baker.make(Zrodlo)
    pusty2 = baker.make(Zrodlo)
    z_pub = baker.make(Zrodlo)
    baker.make(Wydawnictwo_Ciagle, zrodlo=z_pub)

    resp = admin_client.post(
        "/admin/bpp/zrodlo/",
        {
            "action": "usun_zrodla_bez_publikacji_action",
            "select_across": "1",
            "index": "0",
            "_selected_action": [str(z_pub.pk)],  # ignorowane przy select_across
        },
    )
    assert resp.status_code in (200, 302)
    assert not Zrodlo.objects.filter(pk=pusty1.pk).exists()
    assert not Zrodlo.objects.filter(pk=pusty2.pk).exists()
    assert Zrodlo.objects.filter(pk=z_pub.pk).exists()


@pytest.mark.django_db
def test_admin_action_kasuje_wsadowo_po_batchu(admin_client, monkeypatch):
    """Akcja admina kasuje w paczkach (USUN_ZRODLA_BATCH). Wymuszamy mały batch,
    by przejść przez wiele przebiegów — każda paczka commituje się osobno, więc
    padnięcie requestu na dużym zbiorze nie cofa całego postępu.

    Test przechodzi wiele paczek (5 źródeł, batch=2 → 3 przebiegi) i sprawdza,
    że wszystkie puste źródła zniknęły, a źródło z publikacją zostało."""
    from bpp.admin import zrodlo as zrodlo_admin

    monkeypatch.setattr(zrodlo_admin, "USUN_ZRODLA_BATCH", 2)

    puste = [baker.make(Zrodlo) for _ in range(5)]
    z_pub = baker.make(Zrodlo)
    baker.make(Wydawnictwo_Ciagle, zrodlo=z_pub)

    resp = admin_client.post(
        "/admin/bpp/zrodlo/",
        {
            "action": "usun_zrodla_bez_publikacji_action",
            "select_across": "1",
            "index": "0",
            "_selected_action": [str(z_pub.pk)],
        },
    )
    assert resp.status_code in (200, 302)
    assert Zrodlo.objects.filter(pk__in=[z.pk for z in puste]).count() == 0
    assert Zrodlo.objects.filter(pk=z_pub.pk).exists()

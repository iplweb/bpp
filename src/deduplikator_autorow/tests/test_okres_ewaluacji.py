"""Priorytet kandydatów na duplikaty wg okresu ewaluacji (pasek okresu)."""

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from deduplikator_autorow.models import DuplicateScanRun
from deduplikator_autorow.tasks import (
    _calculate_priority_from_meta,
    _przejmij_slot_skanu,
    calculate_author_priority,
    lata_skanu,
    okres_skanu,
)
from ewaluacja_common.models import OkresEwaluacji
from ewaluacja_common.okres import okres_domyslny


@pytest.fixture
def okres_2022():
    return OkresEwaluacji.objects.get(rok_od=2022, rok_do=2025)


@pytest.fixture
def okres_2026():
    return OkresEwaluacji.objects.get(rok_od=2026, rok_do=2030)


@pytest.fixture
def autor_z_praca_2027(autor_maker, wydawnictwo_ciagle, jednostka):
    autor = autor_maker(nazwisko="Okresowy", imiona="Jan")
    wydawnictwo_ciagle.rok = 2027
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.dodaj_autora(autor, jednostka)
    return autor


@pytest.mark.django_db
def test_calculate_author_priority_wg_lat_okresu(autor_z_praca_2027):
    assert calculate_author_priority(autor_z_praca_2027, 2022, 2025) == 0
    assert calculate_author_priority(autor_z_praca_2027, 2026, 2030) == 50

    baker.make(
        "bpp.Autor_Dyscyplina",
        autor=autor_z_praca_2027,
        rok=2027,
    )
    assert calculate_author_priority(autor_z_praca_2027, 2026, 2030) == 100
    assert calculate_author_priority(autor_z_praca_2027, 2022, 2025) == 0


def test_calculate_priority_from_meta_wg_lat_okresu():
    bez_dyscypliny = {"lata_publikacji": {2023, 2027}, "ma_dyscypline": False}
    assert _calculate_priority_from_meta(bez_dyscypliny, 2026, 2030) == 50

    z_dyscyplina = {"lata_publikacji": {2027}, "ma_dyscypline": True}
    assert _calculate_priority_from_meta(z_dyscyplina, 2022, 2025) == 0
    assert _calculate_priority_from_meta(z_dyscyplina, 2026, 2030) == 100


@pytest.mark.django_db
def test_okres_skanu(okres_2022, okres_2026):
    # Bez wcześniejszych skanów i bez pk — okres domyślny.
    assert okres_skanu() == okres_domyslny()
    # Podany pk (skan uruchomiony ze strony) wygrywa.
    assert okres_skanu(okres_2022.pk) == okres_2022
    # Nieistniejący pk — okres domyślny.
    assert okres_skanu(999_999) == okres_domyslny()

    # Nocny skan (bez pk) kontynuuje okres ostatniego skanu.
    DuplicateScanRun.objects.create(
        status=DuplicateScanRun.Status.COMPLETED, okres=okres_2022
    )
    assert okres_skanu() == okres_2022


@pytest.mark.django_db
def test_skan_zapamietuje_okres(okres_2022):
    scan_run = _przejmij_slot_skanu(user=None, celery_task_id="x", okres=okres_2022)
    scan_run.refresh_from_db()
    assert scan_run.okres == okres_2022
    assert lata_skanu(scan_run) == (2022, 2025)


@pytest.mark.django_db
def test_lata_skanu_bez_okresu_to_okres_domyslny():
    scan_run = DuplicateScanRun.objects.create(status=DuplicateScanRun.Status.RUNNING)
    domyslny = okres_domyslny()
    assert lata_skanu(scan_run) == (domyslny.rok_od, domyslny.rok_do)


def _login_user_with_group(client):
    user = baker.make("bpp.BppUser", is_active=True)
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)
    client.force_login(user)
    return user


@pytest.mark.django_db
def test_start_scan_przekazuje_okres_z_adresu(client, mocker, okres_2022):
    """Skan uruchomiony ze strony okresu 2022–2025 liczy priorytet dla tego
    okresu — zadanie dostaje pk okresu (nie czyta sesji)."""
    user = _login_user_with_group(client)
    mocker.patch(
        "deduplikator_autorow.views.scan.is_pbn_people_data_fresh",
        return_value=(True, "", None),
    )
    apply_async = mocker.patch(
        "deduplikator_autorow.tasks.scan_for_duplicates.apply_async",
        side_effect=lambda **kw: mocker.Mock(id=kw["task_id"]),
    )

    response = client.post("/deduplikator_autorow/2022-2025/start-scan/")

    assert response.status_code == 302
    assert apply_async.call_args.kwargs["kwargs"] == {
        "user_id": user.pk,
        "okres_pk": okres_2022.pk,
    }


@pytest.mark.django_db
def test_widok_ostrzega_gdy_skan_liczony_dla_innego_okresu(
    client, okres_2022, okres_2026
):
    _login_user_with_group(client)
    DuplicateScanRun.objects.create(
        status=DuplicateScanRun.Status.COMPLETED,
        finished_at=timezone.now(),
        okres=okres_2022,
    )

    response = client.get("/deduplikator_autorow/2026-2030/duplicate-authors/")
    assert response.status_code == 200
    assert response.context["rok_od"] == 2026
    assert response.context["rok_do"] == 2030
    assert response.context["okres_skanu_inny"] is True
    assert "Uruchom nowe skanowanie, aby" in response.content.decode()

    response = client.get("/deduplikator_autorow/2022-2025/duplicate-authors/")
    assert response.context["okres_skanu_inny"] is False
    assert "Uruchom nowe skanowanie, aby" not in response.content.decode()

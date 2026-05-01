"""Testy filtra mode w widoku duplicate_authors."""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from deduplikator_autorow.models import DuplicateCandidate, DuplicateScanRun


@pytest.fixture
def auth_client(client, db):
    user = baker.make("bpp.BppUser", is_active=True)
    user.set_password("xx")
    user.save()
    grp, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(grp)
    client.force_login(user)
    return client


@pytest.fixture
def scan_with_both_modes(db):
    scan = DuplicateScanRun.objects.create(
        status=DuplicateScanRun.Status.COMPLETED,
        finished_at=timezone.now(),
    )
    a1 = baker.make("bpp.Autor", nazwisko="Pbn1", imiona="Jan")
    a2 = baker.make("bpp.Autor", nazwisko="Pbn1", imiona="Jan")
    g1 = baker.make("bpp.Autor", nazwisko="Gen1", imiona="Anna")
    g2 = baker.make("bpp.Autor", nazwisko="Gen1", imiona="Anna")
    DuplicateCandidate.objects.create(
        scan_run=scan,
        main_autor=a1,
        duplicate_autor=a2,
        confidence_score=80,
        confidence_percent=0.6,
        main_autor_name="Pbn1 Jan",
        duplicate_autor_name="Pbn1 Jan",
        scan_mode="pbn",
    )
    DuplicateCandidate.objects.create(
        scan_run=scan,
        main_autor=g1,
        duplicate_autor=g2,
        confidence_score=80,
        confidence_percent=0.6,
        main_autor_name="Gen1 Anna",
        duplicate_autor_name="Gen1 Anna",
        scan_mode="general",
    )
    return scan


def test_view_mode_filter_pbn(auth_client, scan_with_both_modes):
    response = auth_client.get(
        reverse("deduplikator_autorow:duplicate_authors") + "?mode=pbn"
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "Pbn1" in content
    assert "Gen1" not in content


def test_view_mode_filter_general(auth_client, scan_with_both_modes):
    response = auth_client.get(
        reverse("deduplikator_autorow:duplicate_authors") + "?mode=general"
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "Gen1" in content
    assert "Pbn1" not in content


def test_view_mode_filter_both_default(auth_client, scan_with_both_modes):
    """Default mode (no GET param) — pokazuje któryś (zwykle pierwszy w sort order)."""
    response = auth_client.get(reverse("deduplikator_autorow:duplicate_authors"))
    assert response.status_code == 200
    # Powinien być w kontekście choć jeden z dwóch
    content = response.content.decode()
    assert "Pbn1" in content or "Gen1" in content


def test_view_pending_counters_split_by_mode(auth_client, scan_with_both_modes):
    """Counters per-tryb."""
    response = auth_client.get(reverse("deduplikator_autorow:duplicate_authors"))
    assert response.context["pending_pbn_count"] == 1
    assert response.context["pending_general_count"] == 1


def test_view_invalid_mode_falls_back_to_both(auth_client, scan_with_both_modes):
    response = auth_client.get(
        reverse("deduplikator_autorow:duplicate_authors") + "?mode=zzzunknown"
    )
    assert response.status_code == 200
    assert response.context["mode"] == "both"


def test_view_partial_completed_scan_used(auth_client):
    """get_latest_usable_scan zwraca PARTIAL_COMPLETED."""
    scan = DuplicateScanRun.objects.create(
        status=DuplicateScanRun.Status.PARTIAL_COMPLETED,
        finished_at=timezone.now(),
    )
    a1 = baker.make("bpp.Autor", nazwisko="Sole", imiona="One")
    a2 = baker.make("bpp.Autor", nazwisko="Sole", imiona="One")
    DuplicateCandidate.objects.create(
        scan_run=scan,
        main_autor=a1,
        duplicate_autor=a2,
        confidence_score=80,
        confidence_percent=0.6,
        main_autor_name="x",
        duplicate_autor_name="y",
        scan_mode="pbn",
    )
    response = auth_client.get(reverse("deduplikator_autorow:duplicate_authors"))
    assert response.status_code == 200
    # context "completed_scan" should still be set even though status is PARTIAL_COMPLETED
    # (the field is named completed_scan in the existing view but its semantics are
    # "scan with usable results")
    assert response.context.get("completed_scan") is not None


@pytest.mark.django_db
def test_view_partial_completed_shows_banner(auth_client):
    """View renderuje banner ostrzegający przy PARTIAL_COMPLETED scan."""
    DuplicateScanRun.objects.create(
        status=DuplicateScanRun.Status.PARTIAL_COMPLETED,
        finished_at=timezone.now(),
    )
    response = auth_client.get(reverse("deduplikator_autorow:duplicate_authors"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Częściowo zakończone" in content or "anulowana" in content.lower()


@pytest.mark.django_db
def test_view_mode_filter_radio_present(auth_client, scan_with_both_modes):
    """Mode-filter radio widoczny w HTML."""
    response = auth_client.get(reverse("deduplikator_autorow:duplicate_authors"))
    assert response.status_code == 200
    content = response.content.decode()
    # Radio "PBN", "Ogólny", "Oba" są w widoku
    assert "PBN" in content
    assert "Ogólny" in content
    # Counters w widoku
    assert response.context["pending_pbn_count"] == 1
    assert response.context["pending_general_count"] == 1

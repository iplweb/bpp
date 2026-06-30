"""Testy charakteryzujące ``duplicate_authors_view``.

Pinują bieżące zachowanie PRZED refaktorem (zdjęcie ``C901``).
Pokrywają: brak skanu (running / brak), pusty pending, ścieżkę nawigacji,
wyszukiwanie po nazwisku (z wynikami / bez / skip_count poza zakresem),
filtr confidence_band (high/low) oraz allow_merge_all / low_confidence_names.
"""

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
    grp, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(grp)
    client.force_login(user)
    return client


URL = "deduplikator_autorow:duplicate_authors"


def _candidate(scan, main, dup, *, percent, mode="pbn", name="X Y"):
    return DuplicateCandidate.objects.create(
        scan_run=scan,
        main_autor=main,
        duplicate_autor=dup,
        confidence_score=int(percent * 100),
        confidence_percent=percent,
        main_autor_name=name,
        duplicate_autor_name=name,
        scan_mode=mode,
    )


@pytest.mark.django_db
def test_no_completed_scan_no_running(auth_client):
    response = auth_client.get(reverse(URL))
    assert response.status_code == 200
    ctx = response.context
    assert ctx["completed_scan"] is None
    assert ctx["no_scan_available"] is True
    assert ctx["glowny_autor"] is None
    assert ctx["pending_candidates_count"] == 0


@pytest.mark.django_db
def test_no_completed_scan_with_running_shows_info(auth_client):
    DuplicateScanRun.objects.create(
        status=DuplicateScanRun.Status.RUNNING,
        total_authors_to_scan=10,
        authors_scanned=3,
    )
    response = auth_client.get(reverse(URL))
    assert response.status_code == 200
    ctx = response.context
    assert ctx["running_scan"] is not None
    assert ctx["no_scan_available"] is False
    msgs = [m.message for m in ctx["messages"]]
    assert any("Skanowanie w toku" in m for m in msgs)


@pytest.fixture
def completed_scan(db):
    return DuplicateScanRun.objects.create(
        status=DuplicateScanRun.Status.COMPLETED,
        finished_at=timezone.now(),
    )


@pytest.mark.django_db
def test_completed_scan_no_pending_shows_brak(auth_client, completed_scan):
    response = auth_client.get(reverse(URL))
    assert response.status_code == 200
    ctx = response.context
    assert ctx["glowny_autor"] is None
    assert ctx["pending_candidates_count"] == 0
    msgs = [m.message for m in ctx["messages"]]
    assert any("Brak duplikatów do sprawdzenia" in m for m in msgs)


@pytest.fixture
def scan_one_main(completed_scan):
    """Jeden główny autor z dwoma kandydatami: high (0.8) i low (0.3)."""
    main = baker.make("bpp.Autor", nazwisko="Mainowski", imiona="Adam")
    dup_hi = baker.make("bpp.Autor", nazwisko="Mainowski", imiona="Adam")
    dup_lo = baker.make("bpp.Autor", nazwisko="Mainowski", imiona="Adam")
    _candidate(completed_scan, main, dup_hi, percent=0.8, name="Mainowski Adam")
    _candidate(completed_scan, main, dup_lo, percent=0.3, name="Mainowski Adam")
    return completed_scan, main


@pytest.mark.django_db
def test_navigation_default_shows_main_author(auth_client, scan_one_main):
    _scan, main = scan_one_main
    response = auth_client.get(reverse(URL))
    assert response.status_code == 200
    ctx = response.context
    assert ctx["glowny_autor"] == main
    assert ctx["pending_candidates_count"] == 2
    # Per-main band counters: total 2, high (>=0.5) 1, low 1
    assert ctx["candidates_total_for_main"] == 2
    assert ctx["candidates_high_for_main"] == 1
    assert ctx["candidates_low_for_main"] == 1
    # Domyślnie confidence_band == "all" → oba kandydaci widoczni
    assert len(ctx["duplikaty_z_publikacjami"]) == 2
    # allow_merge_all False bo jest low-confidence (0.3 → 30% < 50)
    assert ctx["allow_merge_all"] is False
    assert ctx["low_confidence_names"]


@pytest.mark.django_db
def test_confidence_band_high(auth_client, scan_one_main):
    response = auth_client.get(reverse(URL) + "?confidence=high")
    assert response.status_code == 200
    ctx = response.context
    assert ctx["confidence_band"] == "high"
    # Tylko high (0.8) kandydat
    assert len(ctx["duplikaty_z_publikacjami"]) == 1
    # Wszyscy widoczni mają wysoką pewność → allow_merge_all True
    assert ctx["allow_merge_all"] is True
    assert ctx["low_confidence_names"] == []


@pytest.mark.django_db
def test_confidence_band_low(auth_client, scan_one_main):
    response = auth_client.get(reverse(URL) + "?confidence=low")
    assert response.status_code == 200
    ctx = response.context
    assert ctx["confidence_band"] == "low"
    assert len(ctx["duplikaty_z_publikacjami"]) == 1
    # Widoczny kandydat ma niską pewność → merge zablokowany
    assert ctx["allow_merge_all"] is False
    assert ctx["low_confidence_names"]


@pytest.mark.django_db
def test_invalid_confidence_band_falls_back_to_all(auth_client, scan_one_main):
    response = auth_client.get(reverse(URL) + "?confidence=zzz")
    assert response.context["confidence_band"] == "all"
    assert len(response.context["duplikaty_z_publikacjami"]) == 2


@pytest.mark.django_db
def test_search_lastname_with_results(auth_client, scan_one_main):
    _scan, main = scan_one_main
    response = auth_client.get(reverse(URL) + "?search_lastname=Mainowski")
    assert response.status_code == 200
    ctx = response.context
    assert ctx["search_lastname"] == "Mainowski"
    assert ctx["search_results_count"] == 1
    assert ctx["glowny_autor"] == main
    assert ctx["search_total_authors"] == 1
    assert ctx["search_has_prev"] is False
    assert ctx["search_has_next"] is False


@pytest.mark.django_db
def test_search_lastname_no_results(auth_client, scan_one_main):
    response = auth_client.get(reverse(URL) + "?search_lastname=Nieistnieje")
    assert response.status_code == 200
    ctx = response.context
    assert ctx["search_lastname"] == "Nieistnieje"
    assert ctx["search_results_count"] == 0
    assert ctx["glowny_autor"] is None


@pytest.mark.django_db
def test_search_skip_count_out_of_range_resets(auth_client, scan_one_main):
    _scan, main = scan_one_main
    response = auth_client.get(
        reverse(URL) + "?search_lastname=Mainowski&skip_count=99"
    )
    assert response.status_code == 200
    ctx = response.context
    assert ctx["skip_count"] == 0
    assert ctx["glowny_autor"] == main


@pytest.mark.django_db
def test_search_invalid_skip_count_defaults_zero(auth_client, scan_one_main):
    response = auth_client.get(
        reverse(URL) + "?search_lastname=Mainowski&skip_count=abc"
    )
    assert response.status_code == 200
    assert response.context["skip_count"] == 0


@pytest.mark.django_db
def test_navigation_invalid_skip_count_defaults_zero(auth_client, scan_one_main):
    response = auth_client.get(reverse(URL) + "?skip_count=notanumber")
    assert response.status_code == 200
    assert response.context["skip_count"] == 0
    assert response.context["glowny_autor"] is not None


@pytest.mark.django_db
def test_scientist_set_when_pbn_uid(auth_client, completed_scan):
    from pbn_api.models import Scientist

    sci = baker.make(Scientist)
    main = baker.make("bpp.Autor", nazwisko="Pbnowy", imiona="Jan", pbn_uid=sci)
    dup = baker.make("bpp.Autor", nazwisko="Pbnowy", imiona="Jan")
    _candidate(completed_scan, main, dup, percent=0.8, name="Pbnowy Jan")
    response = auth_client.get(reverse(URL))
    assert response.status_code == 200
    assert response.context["scientist"] == sci

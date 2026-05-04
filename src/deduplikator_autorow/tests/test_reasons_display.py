"""Testy wzbogacania powodów podobieństwa o ikony i ton.

Logika mapowania text -> (icon, tone) musi siedzieć w warstwie Pythona
(views/utils), a nie w nowo utworzonym tag-library `dedup_tags`. Powód:
auto-discovery template-tagów Django wykonuje się raz przy starcie procesu.
Świeżo dodany pakiet `templatetags/` nie jest skanowany ponownie po reloadzie
plików (auto-reloader ładuje moduły, ale nie odświeża cache template-engine).
W rezultacie {% load dedup_tags %} wywala TemplateSyntaxError aż do pełnego
restartu serwera. Trzymanie logiki w views/utils omija ten cache całkowicie.
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
    user.set_password("xx")
    user.save()
    grp, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(grp)
    client.force_login(user)
    return client


@pytest.fixture
def scan_with_orcid_reason(db):
    """Scan z jednym kandydatem zawierającym powód "identyczny ORCID"."""
    scan = DuplicateScanRun.objects.create(
        status=DuplicateScanRun.Status.COMPLETED,
        finished_at=timezone.now(),
    )
    a1 = baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    a2 = baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    DuplicateCandidate.objects.create(
        scan_run=scan,
        main_autor=a1,
        duplicate_autor=a2,
        confidence_score=80,
        confidence_percent=0.6,
        main_autor_name="Kowalski Jan",
        duplicate_autor_name="Kowalski Jan",
        scan_mode="pbn",
        reasons=[
            "identyczny ORCID - to ten sam autor",
            "identyczne nazwisko",
            "wspólne lata publikacji: [2022, 2023]",
        ],
    )
    return scan


def test_enrich_reason_returns_icon_and_tone():
    """Helper enrich_reason zwraca dict z text/icon/tone."""
    from deduplikator_autorow.utils.reason_display import enrich_reason

    result = enrich_reason("identyczny ORCID - to ten sam autor")
    assert result["text"] == "identyczny ORCID - to ten sam autor"
    assert result["icon"] == "fi-key"
    assert result["tone"] == "match"


def test_enrich_reason_orcid_difference_is_warn():
    """Różny ORCID to mocna negatywna przesłanka -> warn."""
    from deduplikator_autorow.utils.reason_display import enrich_reason

    result = enrich_reason("różny ORCID - to różni autorzy")
    assert result["icon"] == "fi-x-circle"
    assert result["tone"] == "warn"


def test_enrich_reason_unknown_text_falls_back():
    """Nieznany tekst dostaje neutralną ikonę i ton info."""
    from deduplikator_autorow.utils.reason_display import enrich_reason

    result = enrich_reason("zupełnie nieznany powód xyz")
    assert result["icon"] == "fi-info"
    assert result["tone"] == "info"


def test_view_renders_reason_chips_with_icons(auth_client, scan_with_orcid_reason):
    """Widok renderuje powody jako chipy z ikonami Foundation.

    Ten test by w praktyce złapał regresję typu
    'TemplateSyntaxError: dedup_tags is not a registered tag library' —
    bo wywalenie szablonu na {% load %} zwróciłoby 500, nie 200, a brak ikony
    fi-key dla powodu z ORCID-em sygnalizuje że enrichment nie zadziałał.
    """
    response = auth_client.get(reverse("deduplikator_autorow:duplicate_authors"))
    assert response.status_code == 200, (
        "Widok zwrócił błąd — najczęstsza przyczyna to "
        "TemplateSyntaxError z {% load dedup_tags %}"
    )
    content = response.content.decode()
    assert "fi-key" in content, "Brak ikony ORCID (fi-key) w wyrenderowanej stronie"
    assert "deduplikator-autorow__reason-chip--match" in content, (
        "Brak chipa w tonie 'match' — enrichment powodów nie działa"
    )

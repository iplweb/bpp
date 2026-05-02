"""Testy stanu "Scal wszystkie" — gating po pewności + dane potrzebne JS-owi
do odświeżenia stanu po AJAX-owym usunięciu karty (refreshMergeAllAvailability).

Testy są server-side: sprawdzają dane, które view eksportuje do template-a,
a template do DOM-u. Zapewniają, że klient ma wszystko czego potrzebuje, żeby
prawidłowo przeliczyć stan przycisków bez przeładowania strony.

Testowy E2E (kliknięcie "Nie jest duplikatem" + sprawdzenie odblokowania)
żyje w `test_merge_all_refresh_e2e.py` (Playwright).
"""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from deduplikator_autorow.models import DuplicateCandidate, DuplicateScanRun
from deduplikator_autorow.views import MIN_PEWNOSC_DO_WYSWIETLENIA


@pytest.fixture
def auth_client(client, db):
    user = baker.make("bpp.BppUser", is_active=True)
    user.set_password("xx")
    user.save()
    grp, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(grp)
    client.force_login(user)
    return client


def _create_candidate(scan, main, dup, confidence_percent, mode="pbn"):
    """confidence_percent in 0..1 - musi przejść przez display=round(*100)."""
    return DuplicateCandidate.objects.create(
        scan_run=scan,
        main_autor=main,
        duplicate_autor=dup,
        confidence_score=int(confidence_percent * 100),  # nieistotne dla display
        confidence_percent=confidence_percent,
        main_autor_name=str(main),
        duplicate_autor_name=str(dup),
        scan_mode=mode,
    )


@pytest.fixture
def scan_with_mixed_confidence(db):
    """Scan: 1 main author + 2 duplikaty (jeden 80%, jeden 30%)."""
    scan = DuplicateScanRun.objects.create(
        status=DuplicateScanRun.Status.COMPLETED,
        finished_at=timezone.now(),
    )
    main = baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    high = baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    low = baker.make("bpp.Autor", nazwisko="Kowal", imiona="Janusz")
    high_cand = _create_candidate(scan, main, high, 0.80)
    low_cand = _create_candidate(scan, main, low, 0.30)
    return scan, main, high, low, high_cand, low_cand


@pytest.fixture
def scan_only_high_confidence(db):
    """Scan: 1 main + 2 duplikaty - oba ≥ 50%."""
    scan = DuplicateScanRun.objects.create(
        status=DuplicateScanRun.Status.COMPLETED,
        finished_at=timezone.now(),
    )
    main = baker.make("bpp.Autor", nazwisko="Nowak", imiona="Anna")
    a = baker.make("bpp.Autor", nazwisko="Nowak", imiona="Anna")
    b = baker.make("bpp.Autor", nazwisko="Nowak", imiona="Ania")
    _create_candidate(scan, main, a, 0.85)
    _create_candidate(scan, main, b, 0.65)
    return scan, main


def test_view_exposes_pewnosc_threshold_to_template(
    auth_client, scan_only_high_confidence
):
    """JS musi znać próg, żeby przeliczyć po fadeOut. Testujemy że jest w DOM-ie."""
    response = auth_client.get(reverse("deduplikator_autorow:duplicate_authors"))
    assert response.status_code == 200
    content = response.content.decode()
    # Wartość MIN_PEWNOSC_DO_WYSWIETLENIA (50) powinna być wstawiona do JS-a
    # jako var MIN_PEWNOSC_THRESHOLD = 50;
    assert f"MIN_PEWNOSC_THRESHOLD = {MIN_PEWNOSC_DO_WYSWIETLENIA}" in content


def test_card_has_data_pewnosc_attribute(auth_client, scan_with_mixed_confidence):
    """Każda karta musi mieć data-pewnosc - JS po fadeOut iteruje po nich."""
    response = auth_client.get(reverse("deduplikator_autorow:duplicate_authors"))
    content = response.content.decode()
    # Wysokopewny: 0.80 * 100 = 80
    assert 'data-pewnosc="80"' in content
    # Niskopewny: 0.30 * 100 = 30
    assert 'data-pewnosc="30"' in content


def test_card_has_data_author_name_attribute(auth_client, scan_with_mixed_confidence):
    """Każda karta ma data-author-name dla aktualizowanej listy w alercie."""
    response = auth_client.get(reverse("deduplikator_autorow:duplicate_authors"))
    content = response.content.decode()
    # Sprawdzamy że atrybut jest, z dowolnym sensownym tekstem reprezentującym autora
    assert "data-author-name=" in content


def test_merge_all_disabled_when_low_confidence_present(
    auth_client, scan_with_mixed_confidence
):
    """Z 30% kandydatem przyciski 'Scal wszystkie' są wyszarzone."""
    response = auth_client.get(reverse("deduplikator_autorow:duplicate_authors"))
    content = response.content.decode()
    assert 'aria-disabled="true"' in content
    assert "deduplikator-autorow__merge-all-btn--disabled" in content


def test_low_confidence_names_in_data_attribute(
    auth_client, scan_with_mixed_confidence
):
    """data-low-confidence-names przekazuje listę nazwisk do alertu JS."""
    response = auth_client.get(reverse("deduplikator_autorow:duplicate_authors"))
    content = response.content.decode()
    assert "data-low-confidence-names=" in content
    # Zawiera autora 30% (Kowal Janusz)
    assert "30%" in content


def test_merge_all_enabled_when_all_high_confidence(
    auth_client, scan_only_high_confidence
):
    """Wszyscy kandydaci ≥ 50% - przyciski aktywne, brak klasy disabled."""
    response = auth_client.get(reverse("deduplikator_autorow:duplicate_authors"))
    content = response.content.decode()
    # Przyciski merge-all renderują się
    assert 'data-merge-all="true"' in content
    # Atrybut HTML aria-disabled="true" w button-tagach NIE występuje obok
    # przycisków merge-all. Klasa __merge-all-btn--disabled występuje też jako
    # string w JS-ie (dla manipulacji classList), więc asercję robimy
    # znajdując każdy <button data-merge-all="true" ...> i sprawdzając, że
    # nie zawiera klasy disabled w atrybucie class.
    import re

    button_tags = re.findall(r'<button[^>]*data-merge-all="true"[^>]*>', content)
    assert button_tags, "Nie znalazłem ani jednego przycisku merge-all w HTML"
    for tag in button_tags:
        assert "merge-all-btn--disabled" not in tag, (
            f"Przycisk ma klasę disabled mimo że wszyscy ≥ 50%: {tag}"
        )
        assert 'aria-disabled="true"' not in tag, (
            f"Przycisk ma aria-disabled mimo że wszyscy ≥ 50%: {tag}"
        )


def test_view_does_not_render_merge_all_when_no_candidates(auth_client, db):
    """Gdy nie ma kandydatów pending, sekcja merge-all w ogóle się nie renderuje."""
    DuplicateScanRun.objects.create(
        status=DuplicateScanRun.Status.COMPLETED,
        finished_at=timezone.now(),
    )
    response = auth_client.get(reverse("deduplikator_autorow:duplicate_authors"))
    content = response.content.decode()
    # `data-merge-all` jako string występuje w JS-ie; szukamy konkretnego
    # atrybutu HTML w button-tagu.
    import re

    button_tags = re.findall(r'<button[^>]*data-merge-all="true"[^>]*>', content)
    assert not button_tags, (
        f"Nie powinno być przycisków merge-all bez kandydatów, znalazłem: {button_tags}"
    )


def test_pewnosc_display_is_clamped_to_0_100(auth_client, db):
    """confidence_percent > 1.0 (historyczne dane) musi być sklampowany do 100%."""
    scan = DuplicateScanRun.objects.create(
        status=DuplicateScanRun.Status.COMPLETED,
        finished_at=timezone.now(),
    )
    main = baker.make("bpp.Autor", nazwisko="X", imiona="Y")
    dup = baker.make("bpp.Autor", nazwisko="X", imiona="Y")
    DuplicateCandidate.objects.create(
        scan_run=scan,
        main_autor=main,
        duplicate_autor=dup,
        confidence_score=300,  # Surowy score > MAX_PEWNOSC
        confidence_percent=1.4,  # Powinno być sklampowane przy display
        main_autor_name="x",
        duplicate_autor_name="x",
        scan_mode="pbn",
    )
    response = auth_client.get(reverse("deduplikator_autorow:duplicate_authors"))
    content = response.content.decode()
    assert 'data-pewnosc="100"' in content
    assert 'data-pewnosc="140"' not in content

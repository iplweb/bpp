"""Testy widoków przeglądarki ewaluacji.

Ten moduł zawiera testy dla widoków HTTP przeglądarki ewaluacji, w tym:
- EvaluationBrowserView - główny widok przeglądarki
- browser_summary - HTMX partial dla podsumowania
- browser_table - HTMX partial dla tabeli publikacji
- browser_toggle_pin - endpoint do zmiany przypięcia
- browser_swap_discipline - endpoint do zmiany dyscypliny
- browser_recalc_status - endpoint statusu przeliczania
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import (
    Autor_Dyscyplina,
    Dyscyplina_Naukowa,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
)
from ewaluacja_optymalizacja.models import (
    OptimizationRun,
    StatusPrzegladarkaRecalc,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def uczelnia(db):
    """Utwórz uczelnię testową."""
    return baker.make(Uczelnia, nazwa="Testowa Uczelnia")


@pytest.fixture
def dyscyplina_raportowana(db, uczelnia):
    """Utwórz dyscyplinę raportowaną (liczba_n >= 12)."""
    from ewaluacja_common.models import Rodzaj_Autora
    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Informatyka", kod="11.1")

    # Utwórz rodzaj autora jeśli nie istnieje
    Rodzaj_Autora.objects.get_or_create(
        skrot="N",
        defaults={"nazwa": "Liczony do N", "jest_w_n": True, "sort": 1},
    )

    # Utwórz LiczbaNDlaUczelni z liczba_n >= 12
    LiczbaNDlaUczelni.objects.create(
        uczelnia=uczelnia,
        dyscyplina_naukowa=dyscyplina,
        liczba_n=15,
    )

    return dyscyplina


@pytest.fixture
def autor_z_dyscyplina(db, dyscyplina_raportowana):
    """Utwórz autora z przypisaną dyscypliną."""
    from ewaluacja_common.models import Rodzaj_Autora

    autor = baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    jednostka = baker.make("bpp.Jednostka")

    rodzaj_autora, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="N",
        defaults={"nazwa": "Liczony do N", "jest_w_n": True, "sort": 1},
    )

    # Utwórz Autor_Dyscyplina dla lat 2022-2025
    for rok in range(2022, 2026):
        baker.make(
            Autor_Dyscyplina,
            autor=autor,
            rok=rok,
            dyscyplina_naukowa=dyscyplina_raportowana,
            subdyscyplina_naukowa=None,
            rodzaj_autora=rodzaj_autora,
        )

    return autor, jednostka


@pytest.fixture
def publikacja_ciagle(db, autor_z_dyscyplina, dyscyplina_raportowana):
    """Utwórz publikację ciągłą z autorem."""
    autor, jednostka = autor_z_dyscyplina

    pub = baker.make(
        Wydawnictwo_Ciagle,
        rok=2023,
        tytul_oryginalny="Testowa publikacja ciągła",
    )

    autor_rekord = baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=pub,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina_raportowana,
        afiliuje=True,
        zatrudniony=True,
        przypieta=True,
    )

    return pub, autor_rekord


# =============================================================================
# Testy głównego widoku przeglądarki
# =============================================================================


@pytest.mark.django_db
def test_evaluation_browser_requires_login(client, uczelnia):
    """Test że widok wymaga logowania."""
    url = reverse("ewaluacja_optymalizacja:evaluation-browser")
    response = client.get(url)
    assert response.status_code == 302
    assert "/login/" in response.url or "/accounts/login/" in response.url


@pytest.mark.django_db
def test_evaluation_browser_renders(client, admin_user, uczelnia):
    """Test że widok renderuje się poprawnie."""
    client.force_login(admin_user)
    url = reverse("ewaluacja_optymalizacja:evaluation-browser")
    response = client.get(url)
    assert response.status_code == 200
    assert "Przeglądarka ewaluacji" in response.content.decode()


# =============================================================================
# Testy HTMX partials
# =============================================================================


@pytest.mark.django_db
def test_browser_summary_htmx(client, admin_user, uczelnia, dyscyplina_raportowana):
    """Test HTMX partial dla summary."""
    # Utwórz OptimizationRun
    baker.make(
        OptimizationRun,
        uczelnia=uczelnia,
        dyscyplina_naukowa=dyscyplina_raportowana,
        status="completed",
        total_points=100.0,
    )

    client.force_login(admin_user)
    url = reverse("ewaluacja_optymalizacja:browser-summary")
    response = client.get(url, HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    content = response.content.decode()
    assert "100" in content  # Punkty
    assert "Informatyka" in content  # Nazwa dyscypliny


@pytest.mark.django_db
def test_browser_table_htmx(
    client, admin_user, uczelnia, dyscyplina_raportowana, publikacja_ciagle
):
    """Test HTMX partial dla tabeli."""
    client.force_login(admin_user)
    url = reverse("ewaluacja_optymalizacja:browser-table")
    response = client.get(url, HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    content = response.content.decode()
    assert "Testowa publikacja" in content
    assert "Kowalski" in content


@pytest.mark.django_db
def test_browser_table_with_filters(
    client, admin_user, uczelnia, dyscyplina_raportowana, publikacja_ciagle
):
    """Test tabeli z filtrami."""
    client.force_login(admin_user)
    url = reverse("ewaluacja_optymalizacja:browser-table")

    # Filtr po roku
    response = client.get(url, {"rok": "2023"}, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    assert "Testowa publikacja" in response.content.decode()

    # Filtr po roku bez wyników
    response = client.get(url, {"rok": "2022"}, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    assert "Nie znaleziono publikacji" in response.content.decode()


# =============================================================================
# Testy toggle pin
# =============================================================================


@pytest.mark.django_db
def test_browser_toggle_pin_requires_post(client, admin_user, publikacja_ciagle):
    """Test że toggle pin wymaga POST."""
    _, autor_rekord = publikacja_ciagle

    client.force_login(admin_user)
    url = reverse(
        "ewaluacja_optymalizacja:browser-toggle-pin",
        kwargs={"model_type": "ciagle", "pk": autor_rekord.pk},
    )
    response = client.get(url)
    assert response.status_code == 405  # Method Not Allowed


@pytest.mark.django_db
def test_browser_toggle_pin_invalid_model_type(client, admin_user, uczelnia):
    """Test toggle pin z nieprawidłowym typem modelu."""
    client.force_login(admin_user)
    url = reverse(
        "ewaluacja_optymalizacja:browser-toggle-pin",
        kwargs={"model_type": "invalid", "pk": 1},
    )
    response = client.post(url)
    assert response.status_code == 400
    assert "Nieprawidłowy" in response.content.decode()


@pytest.mark.django_db
def test_browser_toggle_pin_record_not_found(client, admin_user, uczelnia):
    """Test toggle pin gdy rekord nie istnieje."""
    client.force_login(admin_user)
    url = reverse(
        "ewaluacja_optymalizacja:browser-toggle-pin",
        kwargs={"model_type": "ciagle", "pk": 99999},
    )
    response = client.post(url)
    assert response.status_code == 400
    assert "Nie znaleziono" in response.content.decode()


# =============================================================================
# Testy swap discipline
# =============================================================================


@pytest.mark.django_db
def test_browser_swap_discipline_requires_two_disciplines(
    client, admin_user, uczelnia, publikacja_ciagle
):
    """Test że swap wymaga autora z dwoma dyscyplinami."""
    _, autor_rekord = publikacja_ciagle

    client.force_login(admin_user)
    url = reverse(
        "ewaluacja_optymalizacja:browser-swap-discipline",
        kwargs={"model_type": "ciagle", "pk": autor_rekord.pk},
    )
    response = client.post(url)
    assert response.status_code == 400
    assert "tylko jedną dyscyplinę" in response.content.decode()


# =============================================================================
# Testy recalc status
# =============================================================================


@pytest.mark.django_db
def test_browser_recalc_status(client, admin_user, uczelnia, dyscyplina_raportowana):
    """Test statusu przeliczania."""
    # Utwórz status w trakcie
    status = StatusPrzegladarkaRecalc.get_or_create()
    status.rozpocznij("test-task-id", uczelnia, {})

    # Utwórz OptimizationRun jako zakończony
    baker.make(
        OptimizationRun,
        uczelnia=uczelnia,
        dyscyplina_naukowa=dyscyplina_raportowana,
        status="completed",
    )

    client.force_login(admin_user)
    url = reverse("ewaluacja_optymalizacja:browser-recalc-status")
    response = client.get(url, HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    content = response.content.decode()
    # Powinno pokazać zakończenie (1/1 dyscyplin)
    assert "100%" in content or "zakończone" in content.lower()

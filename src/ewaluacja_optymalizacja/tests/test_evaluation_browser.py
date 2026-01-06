"""Testy dla przeglądarki ewaluacji."""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import (
    Autor_Dyscyplina,
    Dyscyplina_Naukowa,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)
from ewaluacja_optymalizacja.models import (
    OptimizationRun,
    StatusPrzegladarkaRecalc,
)
from ewaluacja_optymalizacja.views.evaluation_browser import (
    _author_has_two_disciplines,
    _get_discipline_summary,
    _get_filter_options,
    _get_filtered_publications,
    _get_reported_disciplines,
    _snapshot_discipline_points,
)


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
    rodzaj_autora, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="N",
        defaults={"nazwa": "Liczony do N", "w_pionie_n": True},
    )

    # Utwórz LiczbaNDlaUczelni z liczba_n >= 12
    LiczbaNDlaUczelni.objects.create(
        uczelnia=uczelnia,
        dyscyplina_naukowa=dyscyplina,
        liczba_n=15,
    )

    return dyscyplina


@pytest.fixture
def dyscyplina_druga(db):
    """Utwórz drugą dyscyplinę (subdyscyplina)."""
    return baker.make(Dyscyplina_Naukowa, nazwa="Matematyka", kod="11.2")


@pytest.fixture
def autor_z_dyscyplina(db, dyscyplina_raportowana):
    """Utwórz autora z przypisaną dyscypliną."""
    from ewaluacja_common.models import Rodzaj_Autora

    autor = baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    jednostka = baker.make("bpp.Jednostka")

    rodzaj_autora, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="N",
        defaults={"nazwa": "Liczony do N", "w_pionie_n": True},
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
def autor_dwudyscyplinowy(db, dyscyplina_raportowana, dyscyplina_druga):
    """Utwórz autora z dwoma dyscyplinami."""
    from ewaluacja_common.models import Rodzaj_Autora

    autor = baker.make("bpp.Autor", nazwisko="Nowak", imiona="Anna")
    jednostka = baker.make("bpp.Jednostka")

    rodzaj_autora, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="N",
        defaults={"nazwa": "Liczony do N", "w_pionie_n": True},
    )

    # Utwórz Autor_Dyscyplina z dwoma dyscyplinami
    for rok in range(2022, 2026):
        baker.make(
            Autor_Dyscyplina,
            autor=autor,
            rok=rok,
            dyscyplina_naukowa=dyscyplina_raportowana,
            subdyscyplina_naukowa=dyscyplina_druga,
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


@pytest.fixture
def publikacja_zwarta(db, autor_z_dyscyplina, dyscyplina_raportowana):
    """Utwórz publikację zwartą z autorem."""
    autor, jednostka = autor_z_dyscyplina

    pub = baker.make(
        Wydawnictwo_Zwarte,
        rok=2023,
        tytul_oryginalny="Testowa publikacja zwarta",
    )

    autor_rekord = baker.make(
        Wydawnictwo_Zwarte_Autor,
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
# Testy funkcji pomocniczych
# =============================================================================


@pytest.mark.django_db
def test_get_reported_disciplines_empty(uczelnia):
    """Test gdy nie ma raportowanych dyscyplin."""
    result = _get_reported_disciplines(uczelnia)
    assert result == []


@pytest.mark.django_db
def test_get_reported_disciplines_with_data(uczelnia, dyscyplina_raportowana):
    """Test pobierania raportowanych dyscyplin."""
    result = _get_reported_disciplines(uczelnia)
    assert dyscyplina_raportowana.pk in result


@pytest.mark.django_db
def test_snapshot_discipline_points_empty(uczelnia):
    """Test snapshotu gdy nie ma OptimizationRun."""
    result = _snapshot_discipline_points(uczelnia)
    assert result == {}


@pytest.mark.django_db
def test_snapshot_discipline_points_with_data(uczelnia, dyscyplina_raportowana):
    """Test snapshotu z danymi OptimizationRun."""
    baker.make(
        OptimizationRun,
        uczelnia=uczelnia,
        dyscyplina_naukowa=dyscyplina_raportowana,
        status="completed",
        total_points=150.5,
    )

    result = _snapshot_discipline_points(uczelnia)
    assert str(dyscyplina_raportowana.pk) in result
    assert result[str(dyscyplina_raportowana.pk)] == 150.5


@pytest.mark.django_db
def test_get_discipline_summary_empty(uczelnia):
    """Test podsumowania gdy nie ma danych."""
    result = _get_discipline_summary(uczelnia)
    assert result["disciplines"] == []
    assert result["total_points"] == 0


@pytest.mark.django_db
def test_get_discipline_summary_with_diff(uczelnia, dyscyplina_raportowana):
    """Test podsumowania z obliczeniem diff."""
    # Utwórz OptimizationRun
    baker.make(
        OptimizationRun,
        uczelnia=uczelnia,
        dyscyplina_naukowa=dyscyplina_raportowana,
        status="completed",
        total_points=200.0,
    )

    # Punkty przed (było 180)
    punkty_przed = {str(dyscyplina_raportowana.pk): 180.0}

    result = _get_discipline_summary(uczelnia, punkty_przed)

    assert len(result["disciplines"]) == 1
    assert result["disciplines"][0]["punkty"] == 200.0
    assert result["disciplines"][0]["diff"] == 20.0
    assert result["disciplines"][0]["has_diff"] is True
    assert result["total_points"] == 200.0
    assert result["total_diff"] == 20.0


@pytest.mark.django_db
def test_get_filter_options(uczelnia, dyscyplina_raportowana):
    """Test pobierania opcji filtrów."""
    result = _get_filter_options(uczelnia)

    assert "dyscypliny" in result
    assert "lata" in result
    assert result["lata"] == [2022, 2023, 2024, 2025]
    assert dyscyplina_raportowana in list(result["dyscypliny"])


@pytest.mark.django_db
def test_author_has_two_disciplines_false(autor_z_dyscyplina):
    """Test gdy autor ma jedną dyscyplinę."""
    autor, _ = autor_z_dyscyplina
    result = _author_has_two_disciplines(autor, 2023)
    assert result is False


@pytest.mark.django_db
def test_author_has_two_disciplines_true(autor_dwudyscyplinowy):
    """Test gdy autor ma dwie dyscypliny."""
    autor, _ = autor_dwudyscyplinowy
    result = _author_has_two_disciplines(autor, 2023)
    assert result is True


@pytest.mark.django_db
def test_get_filtered_publications_basic(
    uczelnia, dyscyplina_raportowana, publikacja_ciagle
):
    """Test podstawowego pobierania publikacji."""
    reported_ids = [dyscyplina_raportowana.pk]
    filters = {}

    result = _get_filtered_publications(uczelnia, filters, reported_ids)

    assert len(result) == 1
    assert result[0]["model_type"] == "ciagle"
    assert result[0]["rok"] == 2023
    assert len(result[0]["authors"]) == 1


@pytest.mark.django_db
def test_get_filtered_publications_by_year(
    uczelnia, dyscyplina_raportowana, publikacja_ciagle
):
    """Test filtrowania po roku."""
    reported_ids = [dyscyplina_raportowana.pk]

    # Filtr na 2023 - powinno zwrócić
    result_2023 = _get_filtered_publications(uczelnia, {"rok": "2023"}, reported_ids)
    assert len(result_2023) == 1

    # Filtr na 2022 - nie powinno zwrócić
    result_2022 = _get_filtered_publications(uczelnia, {"rok": "2022"}, reported_ids)
    assert len(result_2022) == 0


@pytest.mark.django_db
def test_get_filtered_publications_by_title(
    uczelnia, dyscyplina_raportowana, publikacja_ciagle
):
    """Test filtrowania po tytule."""
    reported_ids = [dyscyplina_raportowana.pk]

    # Filtr pasujący
    result = _get_filtered_publications(uczelnia, {"tytul": "Testowa"}, reported_ids)
    assert len(result) == 1

    # Filtr niepasujący
    result_none = _get_filtered_publications(
        uczelnia, {"tytul": "NieIstnieje"}, reported_ids
    )
    assert len(result_none) == 0


@pytest.mark.django_db
def test_get_filtered_publications_by_author(
    uczelnia, dyscyplina_raportowana, publikacja_ciagle
):
    """Test filtrowania po nazwisku autora."""
    reported_ids = [dyscyplina_raportowana.pk]

    # Filtr pasujący
    result = _get_filtered_publications(
        uczelnia, {"nazwisko": "Kowalski"}, reported_ids
    )
    assert len(result) == 1

    # Filtr niepasujący
    result_none = _get_filtered_publications(
        uczelnia, {"nazwisko": "Nieistniejący"}, reported_ids
    )
    assert len(result_none) == 0


# =============================================================================
# Testy widoków
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


# =============================================================================
# Testy modelu StatusPrzegladarkaRecalc
# =============================================================================


@pytest.mark.django_db
def test_status_przegladarka_recalc_singleton():
    """Test że StatusPrzegladarkaRecalc jest singletonem."""
    status1 = StatusPrzegladarkaRecalc.get_or_create()
    status2 = StatusPrzegladarkaRecalc.get_or_create()
    assert status1.pk == status2.pk == 1


@pytest.mark.django_db
def test_status_przegladarka_recalc_rozpocznij(uczelnia):
    """Test metody rozpocznij."""
    status = StatusPrzegladarkaRecalc.get_or_create()
    punkty_przed = {"1": 100.0, "2": 200.0}

    status.rozpocznij("test-task-123", uczelnia, punkty_przed)

    status.refresh_from_db()
    assert status.w_trakcie is True
    assert status.task_id == "test-task-123"
    assert status.uczelnia == uczelnia
    assert status.punkty_przed == punkty_przed
    assert status.data_rozpoczecia is not None


@pytest.mark.django_db
def test_status_przegladarka_recalc_zakoncz(uczelnia):
    """Test metody zakoncz."""
    status = StatusPrzegladarkaRecalc.get_or_create()
    status.rozpocznij("test-task", uczelnia, {})

    status.zakoncz("Zakończono pomyślnie")

    status.refresh_from_db()
    assert status.w_trakcie is False
    assert status.data_zakonczenia is not None
    assert status.ostatni_komunikat == "Zakończono pomyślnie"

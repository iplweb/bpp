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


# =============================================================================
# Testy filtra "dyscyplina nieprzypisana"
# =============================================================================


@pytest.fixture
def druga_dyscyplina_raportowana(db, uczelnia):
    """Utwórz drugą dyscyplinę raportowaną."""
    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Matematyka", kod="11.2")

    LiczbaNDlaUczelni.objects.create(
        uczelnia=uczelnia,
        dyscyplina_naukowa=dyscyplina,
        liczba_n=15,
    )

    return dyscyplina


@pytest.fixture
def autor_z_subdyscyplina(db, dyscyplina_raportowana, druga_dyscyplina_raportowana):
    """Utwórz autora z dwiema dyscyplinami (główna + subdyscyplina)."""
    from ewaluacja_common.models import Rodzaj_Autora

    autor = baker.make("bpp.Autor", nazwisko="Nowak", imiona="Anna")
    jednostka = baker.make("bpp.Jednostka")

    rodzaj_autora, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="N",
        defaults={"nazwa": "Liczony do N", "jest_w_n": True, "sort": 1},
    )

    # Utwórz Autor_Dyscyplina z subdyscypliną dla lat 2022-2025
    for rok in range(2022, 2026):
        baker.make(
            Autor_Dyscyplina,
            autor=autor,
            rok=rok,
            dyscyplina_naukowa=dyscyplina_raportowana,  # główna: Informatyka
            subdyscyplina_naukowa=druga_dyscyplina_raportowana,  # sub: Matematyka
            rodzaj_autora=rodzaj_autora,
        )

    return autor, jednostka


@pytest.fixture
def publikacja_autora_z_subdyscyplina(
    db, autor_z_subdyscyplina, dyscyplina_raportowana
):
    """Utwórz publikację dla autora z subdyscypliną.

    Publikacja ma przypisaną dyscyplinę główną (Informatyka).
    """
    autor, jednostka = autor_z_subdyscyplina

    pub = baker.make(
        Wydawnictwo_Ciagle,
        rok=2023,
        tytul_oryginalny="Publikacja autora z subdyscypliną",
    )

    autor_rekord = baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=pub,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina_raportowana,  # przypisana: Informatyka
        afiliuje=True,
        zatrudniony=True,
        przypieta=True,
    )

    return pub, autor_rekord


@pytest.mark.django_db
def test_browser_table_filter_dyscyplina_nieprzypisana_glowna(
    client,
    admin_user,
    uczelnia,
    dyscyplina_raportowana,
    druga_dyscyplina_raportowana,
    autor_z_subdyscyplina,
):
    """Test filtra dyscyplina_nieprzypisana - znajduje po głównej dyscyplinie.

    Autor Nowak ma: główna=Informatyka, subdyscyplina=Matematyka.
    Publikacja ma przypisaną Matematykę (sub).
    Szukamy Informatyki (główna) - filtr powinien znaleźć tę publikację,
    bo autor ma Informatykę dostępną, ale użył Matematyki.
    """
    autor, jednostka = autor_z_subdyscyplina

    # Utwórz publikację z przypisaną subdyscypliną (Matematyka)
    pub = baker.make(
        Wydawnictwo_Ciagle,
        rok=2023,
        tytul_oryginalny="Publikacja z nieprzypisaną główną dyscypliną",
    )
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=pub,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=druga_dyscyplina_raportowana,  # Matematyka (sub)
        afiliuje=True,
        zatrudniony=True,
    )

    client.force_login(admin_user)
    url = reverse("ewaluacja_optymalizacja:browser-table")

    # Filtruj po dyscyplinie nieprzypisanej - Informatyka (główna dyscyplina autora)
    response = client.get(
        url,
        {"dyscyplina_nieprzypisana": str(dyscyplina_raportowana.pk)},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    content = response.content.decode()
    # Powinno znaleźć publikację bo autor ma Informatykę jako główną,
    # ale przypisał Matematykę do publikacji
    assert "Publikacja z nieprzypisaną główną dyscypliną" in content
    assert "Nowak" in content


@pytest.mark.django_db
def test_browser_table_filter_dyscyplina_nieprzypisana_subdyscyplina(
    client,
    admin_user,
    uczelnia,
    druga_dyscyplina_raportowana,
    publikacja_autora_z_subdyscyplina,
):
    """Test filtra dyscyplina_nieprzypisana - znajduje po subdyscyplinie."""
    client.force_login(admin_user)
    url = reverse("ewaluacja_optymalizacja:browser-table")

    # Filtruj po dyscyplinie nieprzypisanej - Matematyka (subdyscyplina autora)
    # Autor ma Matematykę jako subdyscyplinę, ale publikacja ma przypisaną Informatykę
    response = client.get(
        url,
        {"dyscyplina_nieprzypisana": str(druga_dyscyplina_raportowana.pk)},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    content = response.content.decode()
    # Powinno znaleźć publikację bo autor ma Matematykę jako subdyscyplinę
    assert "Publikacja autora z subdyscypliną" in content
    assert "Nowak" in content


@pytest.mark.django_db
def test_browser_table_filter_dyscyplina_nieprzypisana_brak_wynikow(
    client, admin_user, uczelnia, druga_dyscyplina_raportowana, publikacja_ciagle
):
    """Test filtra dyscyplina_nieprzypisana - brak wyników gdy autor nie ma dyscypliny."""
    client.force_login(admin_user)
    url = reverse("ewaluacja_optymalizacja:browser-table")

    # Filtruj po Matematyce - autor Kowalski ma tylko Informatykę
    response = client.get(
        url,
        {"dyscyplina_nieprzypisana": str(druga_dyscyplina_raportowana.pk)},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    content = response.content.decode()
    # Nie powinno znaleźć publikacji Kowalskiego
    assert "Kowalski" not in content
    assert "Nie znaleziono publikacji" in content


@pytest.mark.django_db
def test_browser_table_filter_dyscyplina_nieprzypisana_z_rokiem(
    client,
    admin_user,
    uczelnia,
    dyscyplina_raportowana,
    druga_dyscyplina_raportowana,
    autor_z_subdyscyplina,
):
    """Test filtra dyscyplina_nieprzypisana z filtrem roku.

    Autor Nowak ma: główna=Informatyka, sub=Matematyka.
    Publikacje mają przypisaną Matematykę (sub).
    Szukamy Informatyki (główna) z filtrem roku.
    """
    autor, jednostka = autor_z_subdyscyplina

    # Utwórz publikację na rok 2024 z subdyscypliną (Matematyka)
    pub_2024 = baker.make(
        Wydawnictwo_Ciagle,
        rok=2024,
        tytul_oryginalny="Publikacja z 2024",
    )
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=pub_2024,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=druga_dyscyplina_raportowana,  # Matematyka (sub)
        afiliuje=True,
        zatrudniony=True,
    )

    # Utwórz publikację na rok 2023 z subdyscypliną (Matematyka)
    pub_2023 = baker.make(
        Wydawnictwo_Ciagle,
        rok=2023,
        tytul_oryginalny="Publikacja z 2023",
    )
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=pub_2023,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=druga_dyscyplina_raportowana,  # Matematyka (sub)
        afiliuje=True,
        zatrudniony=True,
    )

    client.force_login(admin_user)
    url = reverse("ewaluacja_optymalizacja:browser-table")

    # Filtruj po roku 2024 i dyscyplinie nieprzypisanej (Informatyka - główna)
    response = client.get(
        url,
        {
            "rok": "2024",
            "dyscyplina_nieprzypisana": str(dyscyplina_raportowana.pk),
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    content = response.content.decode()
    # Powinno znaleźć tylko publikację z 2024
    assert "Publikacja z 2024" in content
    assert "Publikacja z 2023" not in content


@pytest.mark.django_db
def test_browser_table_filter_dyscyplina_przypisana_i_nieprzypisana(
    client,
    admin_user,
    uczelnia,
    dyscyplina_raportowana,
    druga_dyscyplina_raportowana,
    publikacja_autora_z_subdyscyplina,
):
    """Test kombinacji filtrów: dyscyplina przypisana + nieprzypisana."""
    client.force_login(admin_user)
    url = reverse("ewaluacja_optymalizacja:browser-table")

    # Filtruj: dyscyplina przypisana = Informatyka, dyscyplina nieprzypisana = Matematyka
    # Autor Nowak ma: przypisaną Informatykę do publikacji, Matematykę jako subdyscyplinę
    response = client.get(
        url,
        {
            "dyscyplina": str(dyscyplina_raportowana.pk),  # przypisana: Informatyka
            "dyscyplina_nieprzypisana": str(
                druga_dyscyplina_raportowana.pk
            ),  # nieprzypisana: Matematyka
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    content = response.content.decode()
    # Powinno znaleźć publikację Nowaka - ma Informatykę przypisaną i Matematykę w profilu
    assert "Publikacja autora z subdyscypliną" in content
    assert "Nowak" in content


@pytest.mark.django_db
def test_browser_table_filter_dyscyplina_nieprzypisana_inna_dyscyplina_przypisana(
    client,
    admin_user,
    uczelnia,
    dyscyplina_raportowana,
    druga_dyscyplina_raportowana,
    publikacja_autora_z_subdyscyplina,
):
    """Test filtra gdy szukamy po dyscyplinie której autor nie ma w profilu."""
    # Autor Nowak ma: główną = Informatyka, sub = Matematyka
    # Publikacja ma przypisaną Informatykę
    # Tworzymy trzecią dyscyplinę której autor nie ma
    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

    trzecia_dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Fizyka", kod="11.3")
    LiczbaNDlaUczelni.objects.create(
        uczelnia=uczelnia,
        dyscyplina_naukowa=trzecia_dyscyplina,
        liczba_n=15,
    )

    client.force_login(admin_user)
    url = reverse("ewaluacja_optymalizacja:browser-table")

    # Filtruj po Fizyce - autor Nowak nie ma tej dyscypliny
    response = client.get(
        url,
        {"dyscyplina_nieprzypisana": str(trzecia_dyscyplina.pk)},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    content = response.content.decode()
    # Nie powinno znaleźć publikacji Nowaka - nie ma Fizyki w profilu
    assert "Nowak" not in content


@pytest.mark.django_db
def test_browser_table_filter_dyscyplina_nieprzypisana_jednodyscyplinowiec_wykluczony(
    client, admin_user, uczelnia, dyscyplina_raportowana, publikacja_ciagle
):
    """Test że autor z jedną dyscypliną NIE jest znajdowany.

    Filtr dyscyplina_nieprzypisana powinien znajdować tylko dwudyscyplinowców
    (autorów z główną I subdyscypliną). Autorzy z jedną dyscypliną nie mają
    możliwości zamiany dyscyplin, więc nie powinni być znajdowani.

    Autor Kowalski ma TYLKO Informatykę (bez subdyscypliny).
    Publikacja ma przypisaną Informatykę.
    """
    client.force_login(admin_user)
    url = reverse("ewaluacja_optymalizacja:browser-table")

    # Szukamy Informatyki - ale autor Kowalski ma tylko jedną dyscyplinę
    response = client.get(
        url,
        {"dyscyplina_nieprzypisana": str(dyscyplina_raportowana.pk)},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    content = response.content.decode()
    # NIE powinno znaleźć publikacji bo autor nie jest dwudyscyplinowcem
    assert "Kowalski" not in content


@pytest.mark.django_db
def test_browser_table_filter_dyscyplina_nieprzypisana_ta_sama_dyscyplina_wykluczena(
    client,
    admin_user,
    uczelnia,
    dyscyplina_raportowana,
    druga_dyscyplina_raportowana,
    autor_z_subdyscyplina,
):
    """Test że publikacja z przypisaną szukaną dyscypliną NIE jest znajdowana.

    Filtr dyscyplina_nieprzypisana szuka publikacji gdzie autor MÓGŁby użyć
    dyscypliny X, ale przypisał dyscyplinę Y. Jeśli publikacja już ma
    przypisaną szukaną dyscyplinę - nie powinna być znajdowana.

    Autor Nowak ma: główna=Informatyka, sub=Matematyka.
    Publikacja ma przypisaną Informatykę (szukaną dyscyplinę).
    """
    autor, jednostka = autor_z_subdyscyplina

    # Utwórz publikację z przypisaną główną dyscypliną (Informatyka)
    pub = baker.make(
        Wydawnictwo_Ciagle,
        rok=2023,
        tytul_oryginalny="Publikacja z przypisaną szukaną dyscypliną",
    )
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=pub,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina_raportowana,  # Informatyka (szukana)
        afiliuje=True,
        zatrudniony=True,
    )

    client.force_login(admin_user)
    url = reverse("ewaluacja_optymalizacja:browser-table")

    # Szukamy Informatyki - ale publikacja już ma Informatykę przypisaną
    response = client.get(
        url,
        {"dyscyplina_nieprzypisana": str(dyscyplina_raportowana.pk)},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    content = response.content.decode()
    # NIE powinno znaleźć tej publikacji - już ma szukaną dyscyplinę przypisaną
    assert "Publikacja z przypisaną szukaną dyscypliną" not in content

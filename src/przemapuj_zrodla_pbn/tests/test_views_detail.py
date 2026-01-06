"""
Testy widoków szczegółowych i przemapowania źródeł w aplikacji przemapuj_zrodla_pbn.

Ten moduł zawiera testy dla:
- PrzemapujZrodloView - widok przemapowania źródła na inne źródło
- znajdz_podobne_zrodla() - funkcja pomocnicza do wyszukiwania podobnych źródeł
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from przemapuj_zrodla_pbn.views import znajdz_podobne_zrodla


@pytest.mark.django_db
def test_przemapuj_zrodlo_view_requires_login(client):
    """Test czy widok przemapowania wymaga zalogowania"""
    journal = baker.make(
        "pbn_api.Journal", status="DELETED", title="", issn="", eissn="", websiteLink=""
    )
    zrodlo = baker.make("bpp.Zrodlo", pbn_uid=journal)

    url = reverse(
        "przemapuj_zrodla_pbn:przemapuj_zrodlo", kwargs={"zrodlo_id": zrodlo.pk}
    )
    response = client.get(url)

    # Powinno przekierować na login
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_przemapuj_zrodlo_view_get(client, django_user_model):
    """Test czy widok GET przemapowania działa poprawnie"""
    user = baker.make(django_user_model)
    client.force_login(user)

    journal_deleted = baker.make(
        "pbn_api.Journal",
        status="DELETED",
        title="Stara Gazeta",
        issn="",
        eissn="",
        websiteLink="",
    )
    zrodlo_stare = baker.make(
        "bpp.Zrodlo", nazwa="Stara Gazeta", pbn_uid=journal_deleted
    )

    url = reverse(
        "przemapuj_zrodla_pbn:przemapuj_zrodlo", kwargs={"zrodlo_id": zrodlo_stare.pk}
    )
    response = client.get(url)

    assert response.status_code == 200
    assert "Stara Gazeta" in response.content.decode()
    assert "Wybierz źródło docelowe" in response.content.decode()


@pytest.mark.django_db
def test_znajdz_podobne_zrodla_function_categorizes_correctly():
    """Test czy funkcja znajdz_podobne_zrodla kategoryzuje źródła poprawnie"""
    # Źródło skasowane
    journal_deleted = baker.make(
        "pbn_api.Journal",
        status="DELETED",
        title="Test Journal",
        issn="",
        eissn="",
        websiteLink="",
    )

    # Najlepsze: ACTIVE + mniswId
    journal_best = baker.make(
        "pbn_api.Journal",
        status="ACTIVE",
        title="Test Journal A",
        mniswId="12345",
        issn="",
        eissn="",
        websiteLink="",
    )
    baker.make("bpp.Zrodlo", nazwa="Test Journal A", pbn_uid=journal_best)

    # Dobre: ACTIVE bez mniswId
    journal_good = baker.make(
        "pbn_api.Journal",
        status="ACTIVE",
        title="Test Journal B",
        mniswId=None,
        issn="",
        eissn="",
        websiteLink="",
    )
    baker.make("bpp.Zrodlo", nazwa="Test Journal B", pbn_uid=journal_good)

    # Akceptowalne: nie-DELETED
    journal_acceptable = baker.make(
        "pbn_api.Journal",
        status="MERGED",
        title="Test Journal C",
        issn="",
        eissn="",
        websiteLink="",
    )
    baker.make("bpp.Zrodlo", nazwa="Test Journal C", pbn_uid=journal_acceptable)

    results = znajdz_podobne_zrodla(journal_deleted, max_results=10)

    # Sprawdź czy kategorie są zdefiniowane
    assert "zrodla_bpp" in results
    assert "journale_pbn" in results

    # Sprawdź czy każda kategoria ma subcategories
    for subcat in ["najlepsze", "dobre", "akceptowalne"]:
        assert subcat in results["zrodla_bpp"]
        assert subcat in results["journale_pbn"]

    # Sprawdź czy są to listy
    for subcat in ["najlepsze", "dobre", "akceptowalne"]:
        assert isinstance(results["zrodla_bpp"][subcat], list)
        assert isinstance(results["journale_pbn"][subcat], list)


@pytest.mark.django_db
def test_przemapuj_zrodlo_view_post_preview(client, django_user_model):
    """Test czy widok POST z parametrem preview działa"""
    user = baker.make(django_user_model)
    client.force_login(user)

    # Użyj podobnej nazwy i tego samego ISSN aby źródło było znalezione przez algorytm
    journal_deleted = baker.make(
        "pbn_api.Journal",
        status="DELETED",
        title="Test Gazeta",
        issn="1234-5678",
        eissn="",
        websiteLink="",
    )
    zrodlo_stare = baker.make(
        "bpp.Zrodlo", nazwa="Test Gazeta", pbn_uid=journal_deleted, issn="1234-5678"
    )

    # Nazwa zaczyna się od "Test Gazeta" więc będzie znaleziona przez PREFIX matching
    journal_new = baker.make(
        "pbn_api.Journal",
        status="ACTIVE",
        title="Test Gazeta Nowa",
        issn="1234-5678",
        eissn="",
        websiteLink="",
    )
    zrodlo_nowe = baker.make(
        "bpp.Zrodlo", nazwa="Test Gazeta Nowa", pbn_uid=journal_new, issn="1234-5678"
    )

    url = reverse(
        "przemapuj_zrodla_pbn:przemapuj_zrodlo", kwargs={"zrodlo_id": zrodlo_stare.pk}
    )
    response = client.post(
        url, {"typ_wyboru": "zrodlo", "zrodlo_docelowe": zrodlo_nowe.pk, "preview": "1"}
    )

    assert response.status_code == 200
    assert "Podgląd zmian" in response.content.decode()
    assert "Test Gazeta Nowa" in response.content.decode()


@pytest.mark.django_db
def test_przemapuj_zrodlo_view_shows_pbn_links_for_zrodla_bpp(
    client, django_user_model, pbn_uczelnia
):
    """Test czy widok pokazuje linki 'zobacz w PBN' dla źródeł BPP z pbn_uid"""
    user = baker.make(django_user_model)
    client.force_login(user)

    # Źródło skasowane
    journal_deleted = baker.make(
        "pbn_api.Journal",
        status="DELETED",
        title="Skasowana Gazeta",
        issn="1234-5678",
        eissn="",
        websiteLink="",
    )
    zrodlo_stare = baker.make(
        "bpp.Zrodlo", nazwa="Skasowana Gazeta", pbn_uid=journal_deleted
    )

    # Źródło z pbn_uid (powinno mieć link)
    # Musi mieć ten sam ISSN żeby było znalezione przez algoritm wyszukiwania
    journal_with_pbn = baker.make(
        "pbn_api.Journal",
        status="ACTIVE",
        title="Gazeta z PBN",
        issn="1234-5678",
        mniswId=12345,
        eissn="",
        websiteLink="",
    )
    baker.make(
        "bpp.Zrodlo",
        nazwa="Skasowana Gazeta A",
        pbn_uid=journal_with_pbn,
        issn="1234-5678",
    )

    url = reverse(
        "przemapuj_zrodla_pbn:przemapuj_zrodlo", kwargs={"zrodlo_id": zrodlo_stare.pk}
    )
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()

    # Sprawdź czy źródło jest na liście
    assert "Skasowana Gazeta A" in content, (
        "Źródło z podobnym ISSN powinno być na liście"
    )

    # Sprawdź czy jest link "Zobacz w PBN" dla źródła z pbn_uid
    assert "Zobacz w PBN" in content, "Link 'Zobacz w PBN' nie został znaleziony w HTML"
    # Sprawdź czy link zawiera prawidłowy URL (metoda link_do_pbn)
    assert 'target="_blank"' in content


@pytest.mark.django_db
def test_przemapuj_zrodlo_view_shows_pbn_links_for_journale_pbn(
    client, django_user_model, pbn_uczelnia
):
    """Test czy widok poprawnie wyświetla stronę z sugestiami dla journali z PBN"""
    user = baker.make(django_user_model)
    client.force_login(user)

    # Źródło skasowane
    journal_deleted = baker.make(
        "pbn_api.Journal",
        status="DELETED",
        title="Testowa Gazeta",
        issn="1234-5678",
        eissn="",
        websiteLink="",
    )
    zrodlo_stare = baker.make(
        "bpp.Zrodlo", nazwa="Testowa Gazeta", pbn_uid=journal_deleted, issn="1234-5678"
    )

    # Utwórz źródło w BPP które będzie sugestią (z aktywnym PBN)
    journal_active = baker.make(
        "pbn_api.Journal",
        status="ACTIVE",
        title="Testowa Gazeta - Edycja Nowa",
        issn="1234-5678",
        mniswId=12345,
        eissn="",
        websiteLink="",
    )
    baker.make(
        "bpp.Zrodlo",
        nazwa="Testowa Gazeta - Edycja Nowa",
        pbn_uid=journal_active,
        issn="1234-5678",
    )

    url = reverse(
        "przemapuj_zrodla_pbn:przemapuj_zrodlo", kwargs={"zrodlo_id": zrodlo_stare.pk}
    )
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()

    # Test sprawdza podstawową funkcjonalność - widok działa i pokazuje sugestie
    # Powinien być link "Zobacz w PBN" dla źródeł z BPP które mają pbn_uid
    assert "Zobacz w PBN" in content, "Link 'Zobacz w PBN' nie został znaleziony w HTML"

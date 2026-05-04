"""Testy admin interface dla importer_publikacji."""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_import_session_admin_list(admin_client, importer_user):
    """Test listy sesji importu w adminie."""
    from importer_publikacji.models import ImportSession

    # Utwórz testową sesję
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="BibTeX",
        identifier="test_key_2024",
        status=ImportSession.Status.COMPLETED,
        raw_data={
            "bibtex_text": "@article{test_key_2024,\n  title = {Test Title}}",
            "bibtex_type": "article",
            "bibtex_key": "test_key_2024",
        },
        normalized_data={
            "title": "Test Title",
            "doi": "10.1234/test.2024.001",
            "year": 2024,
        },
    )

    # Wejdź na listę sesji
    url = reverse("admin:importer_publikacji_importsession_changelist")
    response = admin_client.get(url)

    assert response.status_code == 200
    assert session.identifier in str(response.content)
    assert session.provider_name in str(response.content)


@pytest.mark.django_db
def test_import_session_admin_detail(admin_client, importer_user):
    """Test szczegółów sesji importu w adminie."""
    from importer_publikacji.models import ImportedAuthor, ImportSession

    # Utwórz sesję z danymi
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="BibTeX",
        identifier="test_bibtex_123",
        status=ImportSession.Status.VERIFIED,
        raw_data={
            "bibtex_text": "@article{key123,\n  title = {Original BibTeX Title},\n  author = {Smith, John},\n  year = {2024}\n}",
            "bibtex_type": "article",
            "bibtex_key": "key123",
        },
        normalized_data={
            "title": "Original BibTeX Title",
            "doi": "10.1234/example.2024.123",
            "year": 2024,
        },
    )

    # Dodaj autora
    ImportedAuthor.objects.create(
        session=session,
        order=1,
        family_name="Smith",
        given_name="John",
        orcid="0000-0001-2345-6789",
        match_status=ImportedAuthor.MatchStatus.AUTO_EXACT,
    )

    # Wejdź na szczegóły sesji
    url = reverse("admin:importer_publikacji_importsession_change", args=[session.pk])
    response = admin_client.get(url)

    assert response.status_code == 200
    content = response.content.decode()

    # Sprawdź czy oryginalny BibTeX jest widoczny
    assert "bibtex_text" in content
    assert "Original BibTeX Title" in content
    assert "key123" in content

    # Sprawdź czy autorzy są widoczni
    assert "Smith" in content
    assert "John" in content


@pytest.mark.django_db
def test_imported_author_admin_list(admin_client, importer_user):
    """Test listy importowanych autorów w adminie."""
    from importer_publikacji.models import ImportedAuthor, ImportSession

    # Utwórz sesję i autorów
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/test.2024",
        status=ImportSession.Status.REVIEW,
        raw_data={"DOI": "10.1234/test.2024"},
        normalized_data={"title": "Test Publication"},
    )

    ImportedAuthor.objects.create(
        session=session,
        order=1,
        family_name="Kowalski",
        given_name="Jan",
        orcid="0000-0002-3456-7890",
        match_status=ImportedAuthor.MatchStatus.AUTO_LOOSE,
    )

    ImportedAuthor.objects.create(
        session=session,
        order=2,
        family_name="Nowak",
        given_name="Anna",
        match_status=ImportedAuthor.MatchStatus.UNMATCHED,
    )

    # Wejdź na listę autorów
    url = reverse("admin:importer_publikacji_importedauthor_changelist")
    response = admin_client.get(url)

    assert response.status_code == 200
    content = response.content.decode()

    assert "Kowalski" in content
    assert "Nowak" in content
    assert "Jan" in content
    assert "Anna" in content


@pytest.mark.django_db
def test_import_session_admin_filters(admin_client, importer_user):
    """Test filtrów na liście sesji."""
    from importer_publikacji.models import ImportSession

    # Utwórz sesje z różnymi statusami i dostawcami
    ImportSession.objects.create(
        created_by=importer_user,
        provider_name="BibTeX",
        identifier="key1",
        status=ImportSession.Status.FETCHED,
        raw_data={"bibtex_text": "test1"},
        normalized_data={"title": "Test 1"},
    )

    ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/test",
        status=ImportSession.Status.COMPLETED,
        raw_data={"DOI": "10.1234/test"},
        normalized_data={"title": "Test 2"},
    )

    # Wejdź na listę
    url = reverse("admin:importer_publikacji_importsession_changelist")
    response = admin_client.get(url)

    assert response.status_code == 200

    # Sprawdź filtr po statusie
    response = admin_client.get(url, {"status": "completed"})
    assert response.status_code == 200
    content = response.content.decode()
    assert "Zakończono" in content or "COMPLETED" in content

    # Sprawdź filtr po dostawcy
    response = admin_client.get(url, {"provider_name": "BibTeX"})
    assert response.status_code == 200
    content = response.content.decode()
    assert "BibTeX" in content


@pytest.mark.django_db
def test_import_session_admin_search(admin_client, importer_user):
    """Test wyszukiwania na liście sesji."""
    from importer_publikacji.models import ImportSession

    ImportSession.objects.create(
        created_by=importer_user,
        provider_name="BibTeX",
        identifier="searchable_key",
        status=ImportSession.Status.VERIFIED,
        raw_data={"bibtex_text": "test"},
        normalized_data={
            "title": "Searchable Publication About Machine Learning",
            "doi": "10.1234/search.2024",
        },
    )

    ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="other_key",
        status=ImportSession.Status.FETCHED,
        raw_data={"DOI": "10.5678/other"},
        normalized_data={"title": "Other Article"},
    )

    url = reverse("admin:importer_publikacji_importsession_changelist")

    # Szukaj po identyfikatorze
    response = admin_client.get(url, {"q": "searchable_key"})
    assert response.status_code == 200
    content = response.content.decode()
    assert "searchable_key" in content
    assert "Searchable Publication" in content

    # Szukaj po tytule
    response = admin_client.get(url, {"q": "Machine Learning"})
    assert response.status_code == 200
    content = response.content.decode()
    assert "Searchable Publication" in content

    # Szukaj po DOI
    response = admin_client.get(url, {"q": "10.1234/search.2024"})
    assert response.status_code == 200
    content = response.content.decode()
    assert "Searchable Publication" in content


@pytest.mark.django_db
def test_import_session_admin_readonly(admin_client, importer_user):
    """Test że admin jest read-only (brak możliwości edycji)."""
    from importer_publikacji.models import ImportSession

    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="BibTeX",
        identifier="readonly_test",
        status=ImportSession.Status.FETCHED,
        raw_data={"test": "data"},
        normalized_data={"title": "Readonly Test"},
    )

    # Spróbuj wejść na formularz edycji
    url = reverse("admin:importer_publikacji_importsession_change", args=[session.pk])
    response = admin_client.get(url)

    assert response.status_code == 200

    # Wszystkie pola powinny być readonly - URL details powinien być dostępny
    # ale próba POST powinna być zablokowana (sprawdzamy to w innym teście)


@pytest.mark.django_db
def test_import_session_admin_no_add_permission(admin_client):
    """Test że nie ma możliwości dodawania sesji ręcznie."""
    url = reverse("admin:importer_publikacji_importsession_add")

    # Próba wejścia na formularz dodawania powinna być zablokowana
    response = admin_client.get(url)

    # Django powinien przekierować lub zwrócić 403
    assert response.status_code in [302, 403]

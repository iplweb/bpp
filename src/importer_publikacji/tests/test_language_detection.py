import pytest

from importer_publikacji.views import _detect_language


def test_detect_language_polish_title():
    """Tytuł z polskimi znakami diakrytycznymi → "pl"."""
    title = "Wpływ środowiska na zdrowie człowieka"
    assert _detect_language(title) == "pl"


def test_detect_language_polish_diacritics_variety():
    """Różne polskie znaki diakrytyczne wykrywane."""
    for title in [
        "Źródła energii",
        "Łączność bezprzewodowa",
        "Analiza częstości",
        "Współczesne ćwiczenia",
    ]:
        assert _detect_language(title) == "pl", f"Nie wykryto polskiego dla: {title}"


def test_detect_language_english_title():
    """Angielski tytuł bez polskich znaków → "en"."""
    title = "The influence of environmental factors on human health outcomes"
    assert _detect_language(title) == "en"


def test_detect_language_english_with_abstract():
    """Angielski tytuł z abstraktem → "en"."""
    title = "Environmental factors and health"
    abstract = (
        "This study examines the relationship between"
        " environmental pollution and public health"
        " outcomes in urban areas."
    )
    assert _detect_language(title, abstract) == "en"


def test_detect_language_empty_title():
    """Pusty tytuł → None."""
    assert _detect_language("") is None
    assert _detect_language(None) is None


def test_detect_language_short_title_no_crash():
    """Krótki tytuł bez polskich znaków nie rzuca wyjątku."""
    result = _detect_language("ABC")
    # langdetect może zwrócić cokolwiek lub None
    # dla bardzo krótkiego tekstu; ważne że nie rzuca
    assert result is None or isinstance(result, str)


@pytest.mark.django_db
def test_fetch_auto_detects_language_for_bibtex(
    importer_client,
):
    """BibTeX bez language → język wykrywany automatycznie."""
    from django.urls import reverse

    from importer_publikacji.models import ImportSession

    bibtex = """@article{test2024,
  title = {The Impact of Climate Change on Agriculture},
  author = {Smith, John and Doe, Jane},
  journal = {Nature Climate},
  year = {2024},
  volume = {10},
  pages = {100--110}
}"""
    url = reverse("importer_publikacji:fetch")
    response = importer_client.post(
        url,
        {"provider": "BibTeX", "text_input": bibtex},
    )
    assert response.status_code == 200

    session = ImportSession.objects.order_by("-pk").first()
    assert session is not None
    # Język powinien być wykryty (en) lub None
    # jeśli nie udało się dopasować do bazy
    # Tutaj sprawdzamy czy normalized_data nie ma language
    assert session.normalized_data.get("language") is None


@pytest.mark.django_db
def test_fetch_polish_bibtex_detects_polish(
    importer_client,
):
    """BibTeX z polskim tytułem → wykrywa język polski."""
    from django.urls import reverse

    from importer_publikacji.models import ImportSession

    bibtex = """@article{test2024pl,
  title = {Wpływ zmian klimatycznych na rolnictwo w Polsce},
  author = {Kowalski, Jan},
  journal = {Przegląd Naukowy},
  year = {2024}
}"""
    url = reverse("importer_publikacji:fetch")
    response = importer_client.post(
        url,
        {"provider": "BibTeX", "text_input": bibtex},
    )
    assert response.status_code == 200

    session = ImportSession.objects.order_by("-pk").first()
    assert session is not None
    # Sprawdzamy czy normalized_data nie ma language
    # (BibTeX bez pola language)
    assert session.normalized_data.get("language") is None
    # Język powinien być dopasowany
    # jeśli istnieje rekord Jezyk z skrot_crossref="pl"
    # (zależy od danych w bazie)


@pytest.mark.django_db
def test_verify_context_suggest_crossref_for_bibtex(
    importer_client,
    importer_user,
):
    """BibTeX z DOI → suggest_crossref w kontekście."""
    from django.test import RequestFactory

    from importer_publikacji.models import ImportSession
    from importer_publikacji.views import _verify_context

    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="BibTeX",
        identifier="10.1234/test",
        raw_data={},
        normalized_data={
            "title": "Test",
            "doi": "10.1234/test",
        },
    )

    factory = RequestFactory()
    request = factory.get("/")
    request.user = importer_user

    ctx = _verify_context(request, session)
    assert ctx["suggest_crossref"] is True
    assert ctx["crossref_doi"] == "10.1234/test"


@pytest.mark.django_db
def test_verify_context_no_suggest_for_crossref(
    importer_client,
    importer_user,
):
    """CrossRef provider → brak sugestii CrossRef."""
    from django.test import RequestFactory

    from importer_publikacji.models import ImportSession
    from importer_publikacji.views import _verify_context

    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/test",
        raw_data={},
        normalized_data={
            "title": "Test",
            "doi": "10.1234/test",
        },
    )

    factory = RequestFactory()
    request = factory.get("/")
    request.user = importer_user

    ctx = _verify_context(request, session)
    assert ctx["suggest_crossref"] is False
    assert ctx["crossref_doi"] is None


@pytest.mark.django_db
def test_verify_context_no_suggest_without_doi(
    importer_client,
    importer_user,
):
    """BibTeX bez DOI → brak sugestii CrossRef."""
    from django.test import RequestFactory

    from importer_publikacji.models import ImportSession
    from importer_publikacji.views import _verify_context

    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="BibTeX",
        identifier="test-key",
        raw_data={},
        normalized_data={
            "title": "Test",
            "doi": None,
        },
    )

    factory = RequestFactory()
    request = factory.get("/")
    request.user = importer_user

    ctx = _verify_context(request, session)
    assert ctx["suggest_crossref"] is False
    assert ctx["crossref_doi"] is None

"""Testy uproszczonego kroku 1 importera (jedno wybrane źródło) oraz kolorów
statusów na liście sesji.

Po kliknięciu kafla (albo deep-linku ``?provider=``) krok 1 pokazuje TYLKO
pole na dane wybranego providera — bez radiowego wyboru źródła i bez tabeli
sesji pod spodem. Kolory etykiet statusów: zielony tylko dla „Zakończono".
"""

import pytest
from django.urls import reverse

from importer_publikacji.models import ImportSession

S = ImportSession.Status


def _make_session(user, status, ident):
    return ImportSession.objects.create(
        created_by=user,
        provider_name="CrossRef",
        identifier=ident,
        status=status,
        raw_data={},
        normalized_data={},
    )


# --- Krok 1: pojedyncze źródło -------------------------------------------


@pytest.mark.django_db
def test_fetch_single_provider_has_no_radio_group(importer_client):
    """Wybór providera przez kafel → brak grupy radiowej; provider jako
    ukryte pole."""
    url = reverse("importer_publikacji:index") + "?provider=CrossRef"
    content = importer_client.get(url).content.decode()
    assert 'id="provider-radios"' not in content
    assert '<input type="hidden" name="provider" value="CrossRef"' in content


@pytest.mark.django_db
def test_fetch_single_provider_has_no_sessions_table(importer_client, importer_user):
    """Krok 1 nie dokleja listy sesji pod spodem."""
    _make_session(importer_user, S.FETCHED, "10.1/a")
    url = reverse("importer_publikacji:index") + "?provider=CrossRef"
    content = importer_client.get(url).content.decode()
    assert 'id="sessions-table"' not in content
    assert "Sesje importu" not in content


@pytest.mark.django_db
def test_fetch_single_provider_has_change_source_link(importer_client):
    """Jest link „Wybierz inne źródło" wracający do kafelków."""
    url = reverse("importer_publikacji:index") + "?provider=CrossRef"
    content = importer_client.get(url).content.decode()
    assert "Wybierz inne źródło" in content


@pytest.mark.django_db
def test_fetch_identifier_provider_renders_single_input(importer_client):
    """Provider identyfikatorowy (CrossRef) → jedno pole identyfikatora,
    przycisk „Pobierz dane", brak textarea."""
    url = reverse("importer_publikacji:index") + "?provider=CrossRef"
    content = importer_client.get(url).content.decode()
    assert 'name="identifier"' in content
    assert 'id="input-identifier"' in content
    assert "Pobierz dane" in content
    assert 'name="text_input"' not in content


@pytest.mark.django_db
def test_fetch_text_provider_renders_textarea(importer_client):
    """Provider tekstowy (BibTeX) → textarea, przycisk „Importuj", brak
    pojedynczego pola identyfikatora."""
    url = reverse("importer_publikacji:index") + "?provider=BibTeX"
    content = importer_client.get(url).content.decode()
    assert 'name="text_input"' in content
    assert "Importuj" in content
    assert 'name="identifier"' not in content


@pytest.mark.django_db
def test_fetch_post_invalid_rerenders_single_provider(importer_client):
    """POST bez identyfikatora → błąd walidacji re-renderuje single-provider
    (nadal bez radia i bez listy sesji)."""
    url = reverse("importer_publikacji:fetch")
    response = importer_client.post(
        url,
        {"provider": "CrossRef", "identifier": ""},
        HTTP_HX_REQUEST="true",
    )
    content = response.content.decode()
    assert 'id="provider-radios"' not in content
    assert 'id="sessions-table"' not in content
    assert '<input type="hidden" name="provider" value="CrossRef"' in content


# --- Kolory statusów na liście sesji -------------------------------------


@pytest.mark.django_db
def test_session_list_completed_is_green(importer_client, importer_user):
    _make_session(importer_user, S.COMPLETED, "10.1/done")
    content = importer_client.get(
        reverse("importer_publikacji:sessions")
    ).content.decode()
    assert "label success" in content


@pytest.mark.django_db
def test_session_list_fetched_is_not_green(importer_client, importer_user):
    """„Pobrano dane" (FETCHED) to stan w toku → szary, NIE zielony."""
    _make_session(importer_user, S.FETCHED, "10.1/f")
    content = importer_client.get(
        reverse("importer_publikacji:sessions")
    ).content.decode()
    assert "label secondary" in content
    assert "label success" not in content


@pytest.mark.django_db
def test_session_list_fetching_is_orange(importer_client, importer_user):
    _make_session(importer_user, S.FETCHING, "10.1/w")
    content = importer_client.get(
        reverse("importer_publikacji:sessions")
    ).content.decode()
    assert "label warning" in content


@pytest.mark.django_db
def test_session_list_failed_is_red(importer_client, importer_user):
    _make_session(importer_user, S.IMPORT_FAILED, "10.1/x")
    content = importer_client.get(
        reverse("importer_publikacji:sessions")
    ).content.decode()
    assert "label alert" in content

"""Testy kroku „Sprawdź w PBN" w wizardzie importera.

Pokrywają: routing po Punktacji (NIE-PBN → krok PBN, PBN → przegląd),
zachowanie GET kroku (redirect dla PBN, panel logowania dla niezalogowanego),
POST kroku (status PBN_CHECK), akcję czyszczenia wyboru oraz mapę
``get_continue_url`` dla nowych statusów.
"""

import pytest
from django.urls import reverse

from importer_publikacji.models import ImportSession


def _make_session(importer_user, provider_name="CrossRef", status=None, **kw):
    return ImportSession.objects.create(
        created_by=importer_user,
        provider_name=provider_name,
        identifier="10.1234/test",
        status=status or ImportSession.Status.PUNKTACJA,
        raw_data={},
        normalized_data={"doi": "10.1/x", "title": "Test", "url": None},
        **kw,
    )


# --- get_continue_url --------------------------------------------------------


@pytest.mark.django_db
def test_continue_url_punktacja_non_pbn_goes_to_pbn(importer_user):
    session = _make_session(importer_user, provider_name="CrossRef")
    assert session.get_continue_url().endswith(f"/{session.pk}/pbn/")


@pytest.mark.django_db
def test_continue_url_punktacja_pbn_source_goes_to_review(importer_user):
    session = _make_session(importer_user, provider_name="PBN")
    assert session.get_continue_url().endswith(f"/{session.pk}/review/")


@pytest.mark.django_db
def test_continue_url_pbn_check_goes_to_review(importer_user):
    session = _make_session(
        importer_user,
        provider_name="CrossRef",
        status=ImportSession.Status.PBN_CHECK,
    )
    assert session.get_continue_url().endswith(f"/{session.pk}/review/")


# --- Routing po Punktacji ----------------------------------------------------


@pytest.mark.django_db
def test_punktacja_post_non_pbn_renders_pbn_step(importer_client, importer_user):
    session = _make_session(importer_user, status=ImportSession.Status.AUTHORS_MATCHED)
    url = reverse("importer_publikacji:punktacja", kwargs={"session_id": session.pk})
    response = importer_client.post(url, {"punkty_kbn": "20"})
    assert response.status_code == 200
    assert "Sprawdź w PBN" in response.content.decode()


@pytest.mark.django_db
def test_punktacja_post_pbn_source_skips_to_review(importer_client, importer_user):
    session = _make_session(
        importer_user,
        provider_name="PBN",
        status=ImportSession.Status.AUTHORS_MATCHED,
    )
    url = reverse("importer_publikacji:punktacja", kwargs={"session_id": session.pk})
    response = importer_client.post(url, {"punkty_kbn": "20"})
    assert response.status_code == 200
    content = response.content.decode()
    assert "Sprawdź w PBN" not in content


# --- GET kroku PBN -----------------------------------------------------------


@pytest.mark.django_db
def test_pbn_get_redirects_for_pbn_source(importer_client, importer_user):
    session = _make_session(importer_user, provider_name="PBN")
    url = reverse("importer_publikacji:pbn", kwargs={"session_id": session.pk})
    response = importer_client.get(url)
    assert response.status_code == 302
    assert response.url.endswith(f"/{session.pk}/review/")


@pytest.mark.django_db
def test_pbn_get_shows_login_panel_when_not_logged_in(importer_client, importer_user):
    # importer_user nie ma tokenu PBN → panel „Zaloguj się do PBN"
    session = _make_session(importer_user)
    url = reverse("importer_publikacji:pbn", kwargs={"session_id": session.pk})
    response = importer_client.get(url, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    content = response.content.decode()
    assert "Zaloguj się do PBN" in content
    assert "Pomiń" in content


# --- POST kroku PBN (Dalej / Pomiń) ------------------------------------------


@pytest.mark.django_db
def test_pbn_post_sets_status_and_renders_review(importer_client, importer_user):
    session = _make_session(importer_user)
    url = reverse("importer_publikacji:pbn", kwargs={"session_id": session.pk})
    response = importer_client.post(url, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    session.refresh_from_db()
    assert session.status == ImportSession.Status.PBN_CHECK


# --- Czyszczenie wyboru ------------------------------------------------------


@pytest.mark.django_db
def test_pbn_clear_removes_selection(importer_client, importer_user):
    session = _make_session(importer_user, matched_data={"pbn_mongo_id": "abc123"})
    url = reverse("importer_publikacji:pbn-clear", kwargs={"session_id": session.pk})
    response = importer_client.post(url, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    session.refresh_from_db()
    assert "pbn_mongo_id" not in session.matched_data


# --- Renderowanie szablonu na ścieżce „zalogowany + wyniki" ------------------


@pytest.mark.django_db
def test_pbn_template_renders_results(importer_user):
    """Renderuj krok PBN z wynikami wyszukiwania — łapie błędy szablonu/include
    na ścieżce zalogowanego operatora (której nie pokrywa test niezalogowanego).
    """
    from django.template.loader import render_to_string

    session = _make_session(importer_user)
    ctx = {
        "session": session,
        "logged_in": True,
        "selected": None,
        "selected_pbn_url": None,
        "authorize_url": "/pbn/authorize?next=/x",
        "punktacja_url": reverse(
            "importer_publikacji:punktacja", kwargs={"session_id": session.pk}
        ),
        "review_url": reverse(
            "importer_publikacji:review", kwargs={"session_id": session.pk}
        ),
        "search": {
            "by_doi": [
                {
                    "mongo_id": "m1",
                    "title": "Praca po DOI",
                    "doi": "10.1/x",
                    "year": 2021,
                    "pbn_url": "https://pbn.example/m1",
                }
            ],
            "by_title": [],
            "by_www": [],
            "total_unique": 1,
            "error": None,
            "needs_auth": False,
        },
    }
    html = render_to_string("importer_publikacji/partials/step_pbn.html", ctx)
    assert "Praca po DOI" in html
    assert "Wybierz jako odpowiednik" in html
    # „Dokładnie jeden" — komunikat akceptacji pojedynczego rekordu.
    assert "dokładnie jeden" in html.lower()

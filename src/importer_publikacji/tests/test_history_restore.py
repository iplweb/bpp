"""Przyciski wstecz/naprzód w przeglądarce (HTMX history restore).

Gdy HTMX przywraca historię po Back/Forward (cache-miss), wysyła GET z
NAGŁÓWKAMI ``HX-Request: true`` ORAZ ``HX-History-Restore-Request: true`` i
oczekuje PEŁNEJ strony (podmienia całe ``<body>``). Widoki kroków, jeśli
patrzą tylko na ``HX-Request``, zwracały wtedy sam fragment (partial) — co
niszczyło layout wizarda i podwajało widżety select2 („drugi select").

Regresja: przy przywracaniu historii widok MUSI zwrócić pełną stronę
(zawierającą kontener ``id="importer-wizard"``), a nie goły partial.
"""

import pytest
from django.urls import reverse

from importer_publikacji.models import ImportSession

WIZARD_WRAPPER = 'id="importer-wizard"'


def _make_session(user, **extra):
    defaults = dict(
        created_by=user,
        provider_name="CrossRef",
        identifier="10.1234/hist",
        raw_data={},
        normalized_data={"title": "Test", "doi": None},
        status=ImportSession.Status.VERIFIED,
    )
    defaults.update(extra)
    return ImportSession.objects.create(**defaults)


@pytest.mark.django_db
def test_source_history_restore_returns_full_page(importer_client, importer_user):
    """Back/Forward na krok źródła → pełna strona z kontenerem wizarda."""
    session = _make_session(importer_user)
    url = reverse("importer_publikacji:source", kwargs={"session_id": session.pk})

    resp = importer_client.get(
        url,
        HTTP_HX_REQUEST="true",
        HTTP_HX_HISTORY_RESTORE_REQUEST="true",
    )
    assert resp.status_code == 200
    body = resp.content.decode()
    assert WIZARD_WRAPPER in body, (
        "history-restore musi zwrócić PEŁNĄ stronę (z #importer-wizard), "
        "nie sam partial"
    )


@pytest.mark.django_db
def test_source_plain_htmx_returns_partial(importer_client, importer_user):
    """Zwykłe żądanie HTMX (bez history-restore) → sam fragment."""
    session = _make_session(importer_user)
    url = reverse("importer_publikacji:source", kwargs={"session_id": session.pk})

    resp = importer_client.get(url, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert WIZARD_WRAPPER not in resp.content.decode(), (
        "żywy HTMX ma zwracać partial (bez #importer-wizard)"
    )


@pytest.mark.django_db
def test_verify_history_restore_returns_full_page(importer_client, importer_user):
    """To samo dla kroku weryfikacji."""
    session = _make_session(importer_user, status=ImportSession.Status.FETCHED)
    url = reverse("importer_publikacji:verify", kwargs={"session_id": session.pk})

    resp = importer_client.get(
        url,
        HTTP_HX_REQUEST="true",
        HTTP_HX_HISTORY_RESTORE_REQUEST="true",
    )
    assert resp.status_code == 200
    assert WIZARD_WRAPPER in resp.content.decode()

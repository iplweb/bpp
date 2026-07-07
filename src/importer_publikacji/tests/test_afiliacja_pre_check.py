"""#438: importer publikacji odmawia utworzenia pracy, gdy dopasowany autor
afiliowałby (``afiliuje=True``) do jednostki nieprzyjmującej afiliacji
(rodzaj „Wydział" z ``autor_moze_afiliowac=False`` albo jednostka obca).

Sprawdzenie jest PRZED uruchomieniem taska Celery — na etapie formularza UI
(``CreateView.post``), więc user dostaje komunikat i może poprawić dopasowanie,
zanim cokolwiek trafi do bazy.
"""

from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, RodzajJednostki
from importer_publikacji.models import ImportedAuthor, ImportSession


@pytest.fixture
def authed_client(client, django_user_model):
    user = baker.make(django_user_model, is_staff=True, is_superuser=True)
    client.force_login(user)
    return client, user


def _sesja_z_autorem(user, jednostka, uczelnia=None):
    session = baker.make(
        ImportSession,
        created_by=user,
        status=ImportSession.Status.REVIEW,
        uczelnia=uczelnia,
    )
    baker.make(
        ImportedAuthor,
        session=session,
        order=0,
        match_status=ImportedAuthor.MatchStatus.MANUAL,
        matched_autor=baker.make(Autor),
        matched_jednostka=jednostka,
    )
    return session


@pytest.mark.django_db
def test_create_blokuje_gdy_autor_afiliuje_do_wydzialu(authed_client, jednostka):
    """Autor dopasowany do jednostki rodzaju „Wydział" (afiliuje=True) →
    task NIE jest enqueueowany, sesja zostaje w REVIEW, user widzi błąd."""
    client, user = authed_client
    jednostka.rodzaj = RodzajJednostki.objects.get(nazwa="Wydział")
    jednostka.save()
    session = _sesja_z_autorem(user, jednostka)

    with patch("importer_publikacji.views.wizard.create_publication_task") as mock_task:
        url = reverse("importer_publikacji:create", kwargs={"session_id": session.pk})
        response = client.post(url, {})

    session.refresh_from_db()
    assert session.status == ImportSession.Status.REVIEW
    mock_task.delay.assert_not_called()
    assert response.status_code == 200
    assert "afiliacj" in response.content.decode().lower()


@pytest.mark.django_db
def test_create_ok_gdy_zwykla_jednostka(authed_client, jednostka):
    """Zwykła jednostka (przyjmuje afiliację) → task enqueueowany normalnie."""
    client, user = authed_client
    session = _sesja_z_autorem(user, jednostka)

    with patch("importer_publikacji.views.wizard.create_publication_task") as mock_task:
        mock_task.delay.return_value.id = "create-task-uuid"
        url = reverse("importer_publikacji:create", kwargs={"session_id": session.pk})
        client.post(url, {})

    session.refresh_from_db()
    assert session.status == ImportSession.Status.CREATING
    mock_task.delay.assert_called_once()


@pytest.mark.django_db
def test_create_ok_gdy_jednostka_obca(
    authed_client, uczelnia_z_obca_jednostka, obca_jednostka
):
    """Obca jednostka → autor dostaje afiliuje=False, więc pre-check nie blokuje
    (mimo skupia_pracownikow=False)."""
    client, user = authed_client
    session = _sesja_z_autorem(user, obca_jednostka, uczelnia=uczelnia_z_obca_jednostka)

    with patch("importer_publikacji.views.wizard.create_publication_task") as mock_task:
        mock_task.delay.return_value.id = "create-task-uuid"
        url = reverse("importer_publikacji:create", kwargs={"session_id": session.pk})
        client.post(url, {})

    session.refresh_from_db()
    assert session.status == ImportSession.Status.CREATING
    mock_task.delay.assert_called_once()


@pytest.mark.django_db
def test_waliduj_afiliacje_sesji_raises_dla_wydzialu(jednostka):
    """Twardy guard współdzielony przez CreateView i _create_publication."""
    from importer_publikacji.views.publikacja import waliduj_afiliacje_sesji

    jednostka.rodzaj = RodzajJednostki.objects.get(nazwa="Wydział")
    jednostka.save()
    session = _sesja_z_autorem(baker.make("bpp.BppUser"), jednostka)

    with pytest.raises(ValidationError):
        waliduj_afiliacje_sesji(session)


@pytest.mark.django_db
def test_waliduj_afiliacje_sesji_ok_dla_zwyklej(jednostka):
    from importer_publikacji.views.publikacja import waliduj_afiliacje_sesji

    session = _sesja_z_autorem(baker.make("bpp.BppUser"), jednostka)
    # Nie powinno rzucić:
    waliduj_afiliacje_sesji(session)

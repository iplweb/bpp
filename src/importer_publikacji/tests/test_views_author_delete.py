"""Testy usuwania pojedynczego wiersza importowanego autora.

Freshdesk #332: gdy CrossRef/DOI zwróci błędny lub pusty wpis autora,
operator musi móc go usunąć z ekranu dopasowania autorów, żeby import
mógł przebiec bez niego.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor
from importer_publikacji.models import ImportedAuthor, ImportSession


def _make_session_with_authors(importer_user, count=3):
    """Helper: sesja z kilkoma importowanymi autorami."""
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/test",
        raw_data={},
        normalized_data={},
    )
    for i in range(count):
        ImportedAuthor.objects.create(
            session=session,
            order=i,
            family_name=f"Testowy{i}",
            given_name=f"Autor{i}",
            match_status=ImportedAuthor.MatchStatus.UNMATCHED,
        )
    return session


@pytest.mark.django_db
def test_delete_author_removes_row(importer_client, importer_user):
    """POST na author-delete usuwa rekord ImportedAuthor z sesji."""
    session = _make_session_with_authors(importer_user, count=3)
    target = session.authors.get(order=1)

    url = reverse(
        "importer_publikacji:author-delete",
        kwargs={"session_id": session.pk, "author_id": target.pk},
    )
    response = importer_client.post(url)

    assert response.status_code == 200
    assert not ImportedAuthor.objects.filter(pk=target.pk).exists()
    # Pozostali autorzy nietknięci
    assert session.authors.count() == 2
    remaining_orders = set(session.authors.values_list("order", flat=True))
    assert remaining_orders == {0, 2}


@pytest.mark.django_db
def test_delete_author_renders_authors_step(importer_client, importer_user):
    """Odpowiedź to przerysowany krok autorów z odświeżonymi statystykami."""
    session = _make_session_with_authors(importer_user, count=2)
    target = session.authors.get(order=0)

    url = reverse(
        "importer_publikacji:author-delete",
        kwargs={"session_id": session.pk, "author_id": target.pk},
    )
    response = importer_client.post(url)

    assert response.status_code == 200
    content = response.content.decode()
    # Po usunięciu jednego z dwóch zostaje jeden autor (ogółem)
    assert "Dopasowanie autorów" in content
    assert session.authors.count() == 1


@pytest.mark.django_db
def test_delete_empty_author(importer_client, importer_user):
    """Można usunąć pusty wpis autora (brak nazwiska/imienia)."""
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/empty",
        raw_data={},
        normalized_data={},
    )
    empty = ImportedAuthor.objects.create(
        session=session,
        order=0,
        family_name="",
        given_name="",
        match_status=ImportedAuthor.MatchStatus.UNMATCHED,
    )

    url = reverse(
        "importer_publikacji:author-delete",
        kwargs={"session_id": session.pk, "author_id": empty.pk},
    )
    response = importer_client.post(url)

    assert response.status_code == 200
    assert session.authors.count() == 0


@pytest.mark.django_db
def test_delete_author_keeps_matched_autor(importer_client, importer_user):
    """Usunięcie wiersza importu nie kasuje powiązanego rekordu Autor."""
    session = _make_session_with_authors(importer_user, count=1)
    autor = baker.make(Autor, nazwisko="Realny", imiona="Autor")
    imported = session.authors.get(order=0)
    imported.matched_autor = autor
    imported.match_status = ImportedAuthor.MatchStatus.MANUAL
    imported.save()

    url = reverse(
        "importer_publikacji:author-delete",
        kwargs={"session_id": session.pk, "author_id": imported.pk},
    )
    response = importer_client.post(url)

    assert response.status_code == 200
    assert not ImportedAuthor.objects.filter(pk=imported.pk).exists()
    # Rekord Autor w BPP nie powinien zostać usunięty (on_delete chroni)
    assert Autor.objects.filter(pk=autor.pk).exists()


@pytest.mark.django_db
def test_delete_author_wrong_session_404(importer_client, importer_user):
    """Autor z innej sesji -> 404 (izolacja sesji)."""
    session_a = _make_session_with_authors(importer_user, count=1)
    session_b = _make_session_with_authors(importer_user, count=1)
    author_b = session_b.authors.first()

    url = reverse(
        "importer_publikacji:author-delete",
        kwargs={"session_id": session_a.pk, "author_id": author_b.pk},
    )
    response = importer_client.post(url)

    assert response.status_code == 404
    # Nic nie usunięto
    assert ImportedAuthor.objects.filter(pk=author_b.pk).exists()


@pytest.mark.django_db
def test_delete_author_requires_permission(client, importer_user):
    """Bez uprawnień import nie wolno usuwać autora."""
    from django.contrib.auth import get_user_model

    session = _make_session_with_authors(importer_user, count=1)
    target = session.authors.first()

    User = get_user_model()
    intruder = User.objects.create_user(username="intruz", password="x")
    client.force_login(intruder)

    url = reverse(
        "importer_publikacji:author-delete",
        kwargs={"session_id": session.pk, "author_id": target.pk},
    )
    response = client.post(url)

    assert response.status_code in (302, 403)
    assert ImportedAuthor.objects.filter(pk=target.pk).exists()

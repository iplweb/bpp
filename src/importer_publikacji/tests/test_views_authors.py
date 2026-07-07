"""Testy widoków importera dotyczące tworzenia autorów dla niedopasowanych
ImportedAuthor (`authors-create-unmatched`).
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka
from importer_publikacji.models import ImportedAuthor, ImportSession


def _make_session_with_unmatched(importer_user, count=2):
    """Helper: sesja z niedopasowanymi autorami."""
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
            match_status=(ImportedAuthor.MatchStatus.UNMATCHED),
        )
    return session


@pytest.mark.django_db
def test_create_unmatched_authors_success(
    importer_client,
    importer_user,
    uczelnia_z_obca_jednostka,
):
    """Tworzenie autorów dla niedopasowanych."""
    session = _make_session_with_unmatched(importer_user)
    obca = uczelnia_z_obca_jednostka.obca_jednostka

    url = reverse(
        "importer_publikacji:authors-create-unmatched",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.post(url)
    assert response.status_code == 200

    # Wszyscy autorzy powinni być dopasowani
    for ia in session.authors.all():
        ia.refresh_from_db()
        assert ia.match_status == ImportedAuthor.MatchStatus.MANUAL
        assert ia.matched_autor is not None
        assert ia.matched_jednostka == obca

    # Rekordy Autor powinny istnieć
    assert Autor.objects.filter(nazwisko="Testowy0").exists()
    assert Autor.objects.filter(nazwisko="Testowy1").exists()

    # Autor_Jednostka powinny istnieć
    for ia in session.authors.all():
        assert Autor_Jednostka.objects.filter(
            autor=ia.matched_autor,
            jednostka=obca,
        ).exists()


@pytest.mark.django_db
def test_create_unmatched_no_obca_jednostka(
    importer_client,
    importer_user,
    uczelnia,
):
    """Brak obcej jednostki -> komunikat błędu."""
    # uczelnia bez obcej jednostki
    assert uczelnia.obca_jednostka is None

    session = _make_session_with_unmatched(importer_user)
    url = reverse(
        "importer_publikacji:authors-create-unmatched",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.post(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "obcej jednostki" in content

    # Autorzy wciąż niedopasowani
    for ia in session.authors.all():
        ia.refresh_from_db()
        assert ia.match_status == ImportedAuthor.MatchStatus.UNMATCHED


@pytest.mark.django_db
def test_create_unmatched_orcid_matches_existing(
    importer_client,
    importer_user,
    uczelnia_z_obca_jednostka,
):
    """ORCID istniejącego Autora -> dopasowanie."""
    obca = uczelnia_z_obca_jednostka.obca_jednostka
    existing = baker.make(
        Autor,
        imiona="Jan",
        nazwisko="Kowalski",
        orcid="0000-0001-2345-6789",
    )

    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/orcid-test",
        raw_data={},
        normalized_data={},
    )
    ImportedAuthor.objects.create(
        session=session,
        order=0,
        family_name="Kowalski",
        given_name="Jan",
        orcid="0000-0001-2345-6789",
        match_status=(ImportedAuthor.MatchStatus.UNMATCHED),
    )

    url = reverse(
        "importer_publikacji:authors-create-unmatched",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.post(url)
    assert response.status_code == 200

    ia = session.authors.first()
    ia.refresh_from_db()
    assert ia.matched_autor == existing
    assert ia.matched_jednostka == obca
    assert ia.match_status == ImportedAuthor.MatchStatus.MANUAL

    # Nie powinien powstać nowy Autor
    assert Autor.objects.filter(orcid="0000-0001-2345-6789").count() == 1


@pytest.mark.django_db
def test_author_create_new_single_row(
    importer_client,
    importer_user,
    uczelnia_z_obca_jednostka,
):
    """Per-wierszowe "Utwórz nowego autora" z modala edycji (Freshdesk
    #383) tworzy Autora dla jednego niedopasowanego wiersza i przypisuje
    go do obcej jednostki, nie ruszając pozostałych wierszy."""
    obca = uczelnia_z_obca_jednostka.obca_jednostka
    session = _make_session_with_unmatched(importer_user, count=2)
    first, second = list(session.authors.order_by("order"))

    url = reverse(
        "importer_publikacji:author-create-new",
        kwargs={"session_id": session.pk, "author_id": first.pk},
    )
    response = importer_client.post(url)
    assert response.status_code == 200

    first.refresh_from_db()
    assert first.match_status == ImportedAuthor.MatchStatus.MANUAL
    assert first.matched_autor is not None
    assert first.matched_autor.nazwisko == "Testowy0"
    assert first.matched_autor.imiona == "Autor0"
    assert first.matched_jednostka == obca
    assert Autor_Jednostka.objects.filter(
        autor=first.matched_autor,
        jednostka=obca,
    ).exists()

    # Drugi wiersz nietknięty — to akcja per-wierszowa.
    second.refresh_from_db()
    assert second.match_status == ImportedAuthor.MatchStatus.UNMATCHED
    assert second.matched_autor is None


@pytest.mark.django_db
def test_author_create_new_with_corrections(
    importer_client,
    importer_user,
    uczelnia_z_obca_jednostka,
):
    """Korekta nazwiska/imion/zapisany_jako w POST przed utworzeniem."""
    session = _make_session_with_unmatched(importer_user, count=1)
    imported = session.authors.first()

    url = reverse(
        "importer_publikacji:author-create-new",
        kwargs={"session_id": session.pk, "author_id": imported.pk},
    )
    response = importer_client.post(
        url,
        {
            "nazwisko": "Poprawiony",
            "imiona": "Jan",
            "zapisany_jako": "Poprawiony J.",
        },
    )
    assert response.status_code == 200

    imported.refresh_from_db()
    assert imported.matched_autor.nazwisko == "Poprawiony"
    assert imported.matched_autor.imiona == "Jan"
    assert imported.zapisany_jako == "Poprawiony J."


@pytest.mark.django_db
def test_author_create_new_orcid_matches_existing(
    importer_client,
    importer_user,
    uczelnia_z_obca_jednostka,
):
    """Per-wierszowe tworzenie z ORCID istniejącego Autora dopasowuje
    istniejącego zamiast tworzyć duplikat."""
    obca = uczelnia_z_obca_jednostka.obca_jednostka
    existing = baker.make(
        Autor,
        imiona="Jan",
        nazwisko="Kowalski",
        orcid="0000-0002-1111-2222",
    )
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/row-orcid",
        raw_data={},
        normalized_data={},
    )
    imported = ImportedAuthor.objects.create(
        session=session,
        order=0,
        family_name="Kowalski",
        given_name="Jan",
        orcid="0000-0002-1111-2222",
        match_status=ImportedAuthor.MatchStatus.UNMATCHED,
    )

    url = reverse(
        "importer_publikacji:author-create-new",
        kwargs={"session_id": session.pk, "author_id": imported.pk},
    )
    response = importer_client.post(url)
    assert response.status_code == 200

    imported.refresh_from_db()
    assert imported.matched_autor == existing
    assert imported.matched_jednostka == obca
    assert imported.match_status == ImportedAuthor.MatchStatus.MANUAL
    assert Autor.objects.filter(orcid="0000-0002-1111-2222").count() == 1


@pytest.mark.django_db
def test_author_create_new_no_obca_jednostka(
    importer_client,
    importer_user,
    uczelnia,
):
    """Brak obcej jednostki -> komunikat błędu w wierszu, autor
    pozostaje niedopasowany."""
    assert uczelnia.obca_jednostka is None
    session = _make_session_with_unmatched(importer_user, count=1)
    imported = session.authors.first()

    url = reverse(
        "importer_publikacji:author-create-new",
        kwargs={"session_id": session.pk, "author_id": imported.pk},
    )
    response = importer_client.post(url)
    assert response.status_code == 200
    assert "obcej jednostki" in response.content.decode()

    imported.refresh_from_db()
    assert imported.match_status == ImportedAuthor.MatchStatus.UNMATCHED
    assert imported.matched_autor is None


@pytest.mark.django_db
def test_create_unmatched_noop_when_all_matched(
    importer_client,
    importer_user,
    uczelnia_z_obca_jednostka,
):
    """Brak niedopasowanych -> nic się nie dzieje."""
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/noop",
        raw_data={},
        normalized_data={},
    )
    autor = baker.make(Autor)
    ImportedAuthor.objects.create(
        session=session,
        order=0,
        family_name="Test",
        given_name="Autor",
        match_status=(ImportedAuthor.MatchStatus.AUTO_EXACT),
        matched_autor=autor,
    )

    autor_count_before = Autor.objects.count()

    url = reverse(
        "importer_publikacji:authors-create-unmatched",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.post(url)
    assert response.status_code == 200
    assert Autor.objects.count() == autor_count_before

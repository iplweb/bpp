import django.db
import pytest

from importer_publikacji.models import (
    ImportedAuthor,
    ImportSession,
)


@pytest.mark.django_db
def test_import_session_str(importer_user):
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/test",
        raw_data={"test": True},
        normalized_data={"title": "Test"},
    )
    result = str(session)
    assert "CrossRef" in result
    assert "10.1234/test" in result


@pytest.mark.django_db
def test_import_session_default_status(importer_user):
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/test",
        raw_data={},
        normalized_data={},
    )
    assert session.status == ImportSession.Status.FETCHED


@pytest.mark.django_db
def test_imported_author_display_name(importer_user):
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/test",
        raw_data={},
        normalized_data={},
    )
    author = ImportedAuthor.objects.create(
        session=session,
        order=0,
        family_name="Kowalski",
        given_name="Jan",
    )
    assert author.display_name == "Kowalski Jan"


@pytest.mark.django_db
def test_imported_author_default_status(importer_user):
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/test",
        raw_data={},
        normalized_data={},
    )
    author = ImportedAuthor.objects.create(
        session=session,
        order=0,
        family_name="Kowalski",
    )
    assert author.match_status == ImportedAuthor.MatchStatus.UNMATCHED


@pytest.mark.django_db
def test_imported_author_unique_order(importer_user):
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/test",
        raw_data={},
        normalized_data={},
    )
    ImportedAuthor.objects.create(session=session, order=0, family_name="A")
    with pytest.raises(django.db.IntegrityError):
        ImportedAuthor.objects.create(session=session, order=0, family_name="B")


@pytest.mark.django_db
def test_import_session_ordering(importer_user):
    s1 = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/first",
        raw_data={},
        normalized_data={},
    )
    s2 = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/second",
        raw_data={},
        normalized_data={},
    )
    sessions = list(ImportSession.objects.all())
    assert sessions[0] == s2  # newer first
    assert sessions[1] == s1

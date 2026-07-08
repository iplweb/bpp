from datetime import timedelta

import django.db
import pytest
from django.utils import timezone
from model_bakery import baker

from importer_publikacji.models import (
    ImportedAuthor,
    ImportSession,
)


def _make_session(user, **kwargs):
    defaults = dict(
        created_by=user,
        provider_name="CrossRef",
        identifier="10.1234/test",
        raw_data={},
        normalized_data={},
    )
    defaults.update(kwargs)
    return ImportSession.objects.create(**defaults)


@pytest.mark.django_db
def test_is_stalled_true_when_fetching_past_threshold(importer_user):
    session = _make_session(importer_user, status=ImportSession.Status.FETCHING)
    # `modified` ≈ teraz; symulujemy upływ czasu przekazując przyszłe `now`.
    future = timezone.now() + timedelta(seconds=10_000)
    assert session.is_stalled(now=future) is True


@pytest.mark.django_db
def test_is_stalled_false_when_recent(importer_user):
    session = _make_session(importer_user, status=ImportSession.Status.FETCHING)
    assert session.is_stalled(now=timezone.now()) is False


@pytest.mark.django_db
def test_is_stalled_true_for_creating(importer_user):
    session = _make_session(importer_user, status=ImportSession.Status.CREATING)
    future = timezone.now() + timedelta(seconds=10_000)
    assert session.is_stalled(now=future) is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status",
    [
        ImportSession.Status.FETCHED,
        ImportSession.Status.IMPORT_FAILED,
        ImportSession.Status.COMPLETED,
        ImportSession.Status.CANCELLED,
    ],
)
def test_is_stalled_false_for_non_inflight_status(importer_user, status):
    # Watchdog dotyczy TYLKO stanów in-flight (FETCHING/CREATING) — stan
    # terminalny nigdy nie jest "zawieszony", choćby `modified` był prastary.
    session = _make_session(importer_user, status=status)
    future = timezone.now() + timedelta(seconds=10_000)
    assert session.is_stalled(now=future) is False


@pytest.mark.django_db
def test_mark_stalled_from_fetching_sets_failed_fetch(importer_user):
    session = _make_session(
        importer_user,
        status=ImportSession.Status.FETCHING,
        celery_task_id="task-uuid-abc",
    )
    session.mark_stalled()
    session.refresh_from_db()
    assert session.status == ImportSession.Status.IMPORT_FAILED
    assert session.last_failed_stage == "fetch"
    assert session.celery_task_id == ""
    assert session.last_error_message  # niepusty, user-safe komunikat
    assert session.last_error_traceback == ""


@pytest.mark.django_db
def test_mark_stalled_from_creating_sets_failed_create(importer_user):
    session = _make_session(
        importer_user,
        status=ImportSession.Status.CREATING,
        celery_task_id="task-uuid-xyz",
    )
    session.mark_stalled()
    session.refresh_from_db()
    assert session.status == ImportSession.Status.IMPORT_FAILED
    assert session.last_failed_stage == "create"
    assert session.celery_task_id == ""


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


@pytest.mark.django_db
def test_import_session_has_async_state_fields():
    session = baker.make(ImportSession)
    # Defaults dla nowych pól
    assert session.celery_task_id == ""
    assert session.last_error_message == ""
    assert session.last_error_traceback == ""
    assert session.last_failed_stage == ""


@pytest.mark.django_db
def test_import_session_status_includes_new_choices():
    choices = dict(ImportSession.Status.choices)
    assert ImportSession.Status.FETCHING in choices
    assert ImportSession.Status.CREATING in choices
    assert ImportSession.Status.IMPORT_FAILED in choices


@pytest.mark.django_db
def test_get_continue_url_fetching_points_to_task_status():
    session = baker.make(
        ImportSession,
        status=ImportSession.Status.FETCHING,
    )
    url = session.get_continue_url()
    assert "task-status" in url
    assert str(session.pk) in url


@pytest.mark.django_db
def test_get_continue_url_creating_points_to_task_status():
    session = baker.make(
        ImportSession,
        status=ImportSession.Status.CREATING,
    )
    url = session.get_continue_url()
    assert "task-status" in url


@pytest.mark.django_db
def test_get_continue_url_import_failed_points_to_task_status():
    session = baker.make(
        ImportSession,
        status=ImportSession.Status.IMPORT_FAILED,
    )
    url = session.get_continue_url()
    # Status view renderuje error partial sam — kierujemy tam.
    assert "task-status" in url


@pytest.mark.django_db
def test_imported_author_domyslnie_autor():
    from bpp import const

    session = baker.make(ImportSession)
    autor = baker.make(ImportedAuthor, session=session, order=0)
    assert autor.typ_ogolny == const.TO_AUTOR


@pytest.mark.django_db
def test_get_continue_url_punktacja_po_autorach():
    s = baker.make(ImportSession, status=ImportSession.Status.AUTHORS_MATCHED)
    assert s.get_continue_url().endswith(f"/{s.pk}/punktacja/")

    s.status = ImportSession.Status.PUNKTACJA
    assert s.get_continue_url().endswith(f"/{s.pk}/review/")

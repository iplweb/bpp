import pytest
from model_bakery import baker

from importer_publikacji.models import (
    EntryStatus,
    ImportSession,
    MultipleWorksImport,
    MultipleWorksImportEntry,
)


@pytest.mark.django_db
def test_entry_status_pending_without_session():
    entry = baker.make(MultipleWorksImportEntry, session=None, skipped=False)
    assert entry.status == EntryStatus.PENDING


@pytest.mark.django_db
def test_entry_status_malformed_when_parse_error():
    entry = baker.make(
        MultipleWorksImportEntry, session=None, parse_error="zepsute", skipped=False
    )
    assert entry.status == EntryStatus.MALFORMED


@pytest.mark.django_db
def test_entry_status_skipped_beats_pending():
    entry = baker.make(MultipleWorksImportEntry, session=None, skipped=True)
    assert entry.status == EntryStatus.SKIPPED


@pytest.mark.django_db
def test_entry_status_imported_when_session_completed():
    session = baker.make(ImportSession, status=ImportSession.Status.COMPLETED)
    entry = baker.make(MultipleWorksImportEntry, session=session)
    assert entry.status == EntryStatus.IMPORTED


@pytest.mark.django_db
def test_entry_status_imported_beats_skipped():
    # Precedencja: IMPORTED > SKIPPED. Ukończona sesja wygrywa nawet gdy
    # wpis oznaczono jako pominięty — zabezpiecza przed cichym przestawieniem
    # kolejności warunków w property `status`.
    session = baker.make(ImportSession, status=ImportSession.Status.COMPLETED)
    entry = baker.make(MultipleWorksImportEntry, session=session, skipped=True)
    assert entry.status == EntryStatus.IMPORTED


@pytest.mark.django_db
def test_entry_status_skipped_beats_malformed():
    # Precedencja: SKIPPED > MALFORMED. Ręczne pominięcie wygrywa nad błędem
    # parsowania — zabezpiecza przed cichym przestawieniem kolejności warunków.
    entry = baker.make(
        MultipleWorksImportEntry,
        session=None,
        skipped=True,
        parse_error="zepsute",
    )
    assert entry.status == EntryStatus.SKIPPED


@pytest.mark.django_db
def test_entry_status_failed_when_session_import_failed():
    session = baker.make(ImportSession, status=ImportSession.Status.IMPORT_FAILED)
    entry = baker.make(MultipleWorksImportEntry, session=session)
    assert entry.status == EntryStatus.FAILED


@pytest.mark.django_db
def test_entry_status_failed_when_session_stalled(monkeypatch):
    session = baker.make(ImportSession, status=ImportSession.Status.FETCHING)
    monkeypatch.setattr(session, "is_stalled", lambda: True)
    entry = MultipleWorksImportEntry(
        parent=baker.make(MultipleWorksImport), order=0, session=session
    )
    assert entry.status == EntryStatus.FAILED


@pytest.mark.django_db
def test_entry_status_cancelled_maps_to_pending():
    session = baker.make(ImportSession, status=ImportSession.Status.CANCELLED)
    entry = baker.make(MultipleWorksImportEntry, session=session)
    assert entry.status == EntryStatus.PENDING


@pytest.mark.django_db
def test_entry_status_in_progress_mid_wizard():
    session = baker.make(ImportSession, status=ImportSession.Status.VERIFIED)
    entry = baker.make(MultipleWorksImportEntry, session=session)
    assert entry.status == EntryStatus.IN_PROGRESS


@pytest.mark.django_db
def test_progress_counts():
    batch = baker.make(MultipleWorksImport)
    done = baker.make(ImportSession, status=ImportSession.Status.COMPLETED)
    baker.make(MultipleWorksImportEntry, parent=batch, order=0, session=done)
    baker.make(MultipleWorksImportEntry, parent=batch, order=1, skipped=True)
    baker.make(MultipleWorksImportEntry, parent=batch, order=2, session=None)
    progress = batch.progress
    assert progress == {"imported": 1, "skipped": 1, "total": 3, "done": False}

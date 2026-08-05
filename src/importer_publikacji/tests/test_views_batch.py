import pytest
from django.urls import reverse
from model_bakery import baker

from importer_publikacji.models import (
    EntryStatus,
    ImportSession,
    MultipleWorksImport,
    MultipleWorksImportEntry,
)
from importer_publikacji.providers import get_provider

TWO_ENTRIES = """@article{a,
  title = {Pierwsza},
  author = {Kowalski, Jan},
  year = {2021},
}

@book{b,
  title = {Druga},
  author = {Nowak, Anna},
  year = {2022},
}"""

ONE_ENTRY = """@article{a,
  title = {Jedyna},
  author = {Kowalski, Jan},
  year = {2021},
}"""


@pytest.fixture
def operator(django_user_model):
    user = baker.make(django_user_model, is_superuser=True, is_staff=True)
    return user


@pytest.mark.django_db
def test_fetch_two_entries_creates_batch_and_hx_redirects(client, operator):
    client.force_login(operator)
    resp = client.post(
        reverse("importer_publikacji:fetch"),
        {"provider": "BibTeX", "text_input": TWO_ENTRIES},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    batch = MultipleWorksImport.objects.get()
    assert batch.entries.count() == 2
    assert MultipleWorksImportEntry.objects.filter(session__isnull=False).count() == 0
    expected = reverse(
        "importer_publikacji:batch-detail", kwargs={"batch_id": batch.pk}
    )
    assert resp["HX-Redirect"] == expected
    # Zaden ImportSession nie powstal (leniwy drip):
    assert ImportSession.objects.count() == 0


@pytest.mark.django_db
def test_fetch_single_entry_unchanged(client, operator):
    client.force_login(operator)
    resp = client.post(
        reverse("importer_publikacji:fetch"),
        {"provider": "BibTeX", "text_input": ONE_ENTRY},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    assert MultipleWorksImport.objects.count() == 0
    session = ImportSession.objects.get()
    assert resp["HX-Redirect"] == reverse(
        "importer_publikacji:task-status", kwargs={"session_id": session.pk}
    )


@pytest.mark.django_db
def test_batch_entry_import_creates_session(client, operator):
    client.force_login(operator)
    # provider_name musi byc zarejestrowanym dostawca — inaczej
    # fetch_session_task (eager w testach) rzuci KeyError z get_provider().
    batch = baker.make(MultipleWorksImport, provider_name="BibTeX")
    entry = baker.make(
        MultipleWorksImportEntry, parent=batch, order=0, raw_bibtex=ONE_ENTRY
    )
    resp = client.post(
        reverse("importer_publikacji:batch-entry-import", kwargs={"entry_id": entry.pk})
    )
    entry.refresh_from_db()
    assert entry.session is not None
    assert entry.session.identifier == ONE_ENTRY
    assert resp.status_code == 302
    assert resp["Location"] == reverse(
        "importer_publikacji:task-status", kwargs={"session_id": entry.session.pk}
    )


@pytest.mark.django_db
def test_batch_entry_import_guards_inflight(client, operator):
    client.force_login(operator)
    batch = baker.make(MultipleWorksImport)
    existing = baker.make(ImportSession, status=ImportSession.Status.FETCHED)
    entry = baker.make(
        MultipleWorksImportEntry, parent=batch, order=0, session=existing
    )
    resp = client.post(
        reverse("importer_publikacji:batch-entry-import", kwargs={"entry_id": entry.pk})
    )
    entry.refresh_from_db()
    # Nie powstala druga sesja; redirect na kontynuacje istniejacej.
    assert entry.session == existing
    assert ImportSession.objects.count() == 1
    assert resp["Location"] == existing.get_continue_url()


@pytest.mark.django_db
def test_batch_entry_import_stalled_session_creates_new(client, operator, settings):
    client.force_login(operator)
    # Sesja utknela: status FETCHING (in-flight), ale przekroczyla prog
    # watchdoga -> is_stalled() == True. Guard NIE powinien redirectowac na
    # kontynuacje martwej sesji, tylko wystartowac import od nowa.
    settings.IMPORTER_STALL_TIMEOUT = 0
    batch = baker.make(MultipleWorksImport, provider_name="BibTeX")
    stalled = baker.make(ImportSession, status=ImportSession.Status.FETCHING)
    entry = baker.make(
        MultipleWorksImportEntry,
        parent=batch,
        order=0,
        raw_bibtex=ONE_ENTRY,
        session=stalled,
    )
    assert stalled.is_stalled() is True
    resp = client.post(
        reverse("importer_publikacji:batch-entry-import", kwargs={"entry_id": entry.pk})
    )
    entry.refresh_from_db()
    # Powstala DRUGA sesja, a entry wskazuje na nowa (nie na utknieta).
    assert ImportSession.objects.count() == 2
    assert entry.session is not None
    assert entry.session != stalled
    assert entry.session.identifier == ONE_ENTRY
    assert resp.status_code == 302
    assert resp["Location"] == reverse(
        "importer_publikacji:task-status", kwargs={"session_id": entry.session.pk}
    )


@pytest.mark.django_db
def test_batch_entry_import_rejects_malformed(client, operator):
    client.force_login(operator)
    batch = baker.make(MultipleWorksImport)
    entry = baker.make(
        MultipleWorksImportEntry, parent=batch, order=0, parse_error="zepsute"
    )
    resp = client.post(
        reverse("importer_publikacji:batch-entry-import", kwargs={"entry_id": entry.pk})
    )
    assert resp.status_code == 400
    entry.refresh_from_db()
    assert entry.session is None


@pytest.mark.django_db
def test_batch_entry_skip_toggles(client, operator):
    client.force_login(operator)
    batch = baker.make(MultipleWorksImport, provider_name="BibTeX")
    entry = baker.make(MultipleWorksImportEntry, parent=batch, order=0, skipped=False)
    url = reverse("importer_publikacji:batch-entry-skip", kwargs={"entry_id": entry.pk})
    resp = client.post(url)
    entry.refresh_from_db()
    assert entry.skipped is True
    assert resp["Location"] == reverse(
        "importer_publikacji:batch-detail", kwargs={"batch_id": batch.pk}
    )
    client.post(url)  # przywroc
    entry.refresh_from_db()
    assert entry.skipped is False


@pytest.mark.django_db
def test_batch_entry_skip_refuses_imported(client, operator):
    client.force_login(operator)
    batch = baker.make(MultipleWorksImport, provider_name="BibTeX")
    done = baker.make(ImportSession, status=ImportSession.Status.COMPLETED)
    entry = baker.make(MultipleWorksImportEntry, parent=batch, order=0, session=done)
    resp = client.post(
        reverse("importer_publikacji:batch-entry-skip", kwargs={"entry_id": entry.pk})
    )
    entry.refresh_from_db()
    assert entry.skipped is False  # niezmienione
    assert resp.status_code == 400


@pytest.mark.django_db
def test_batch_entry_import_refuses_completed(client, operator):
    client.force_login(operator)
    batch = baker.make(MultipleWorksImport, provider_name="BibTeX")
    done = baker.make(ImportSession, status=ImportSession.Status.COMPLETED)
    entry = baker.make(MultipleWorksImportEntry, parent=batch, order=0, session=done)
    resp = client.post(
        reverse("importer_publikacji:batch-entry-import", kwargs={"entry_id": entry.pk})
    )
    entry.refresh_from_db()
    # Nie powstala nowa sesja, entry.session bez zmian, redirect na done.
    assert ImportSession.objects.count() == 1
    assert entry.session == done
    assert resp.status_code == 302
    assert resp["Location"] == done.get_continue_url()


@pytest.mark.django_db
def test_batch_detail_lists_entries_and_progress(client, operator):
    client.force_login(operator)
    batch = baker.make(MultipleWorksImport, provider_name="BibTeX")
    done = baker.make(ImportSession, status=ImportSession.Status.COMPLETED)
    baker.make(
        MultipleWorksImportEntry, parent=batch, order=0, title="Alfa", session=done
    )
    baker.make(MultipleWorksImportEntry, parent=batch, order=1, title="Beta")
    resp = client.get(
        reverse("importer_publikacji:batch-detail", kwargs={"batch_id": batch.pk})
    )
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "Alfa" in content
    assert "Beta" in content
    assert "1 z 2" in content


@pytest.mark.django_db
def test_batch_detail_marks_stalled_session_as_failed(client, operator, settings):
    settings.IMPORTER_STALL_TIMEOUT = 0  # kazda sesja in-flight = stalled
    client.force_login(operator)
    batch = baker.make(MultipleWorksImport, provider_name="BibTeX")
    stuck = baker.make(ImportSession, status=ImportSession.Status.FETCHING)
    entry = baker.make(MultipleWorksImportEntry, parent=batch, order=0, session=stuck)
    client.get(
        reverse("importer_publikacji:batch-detail", kwargs={"batch_id": batch.pk})
    )
    entry.refresh_from_db()
    entry.session.refresh_from_db()
    assert entry.session.status == ImportSession.Status.IMPORT_FAILED
    assert entry.status == EntryStatus.FAILED


@pytest.mark.django_db
def test_done_shows_back_to_batch_link(client, operator):
    client.force_login(operator)
    batch = baker.make(MultipleWorksImport)
    session = baker.make(ImportSession, status=ImportSession.Status.COMPLETED)
    baker.make(MultipleWorksImportEntry, parent=batch, order=0, session=session)
    baker.make(MultipleWorksImportEntry, parent=batch, order=1)
    resp = client.get(
        reverse("importer_publikacji:done", kwargs={"session_id": session.pk})
    )
    content = resp.content.decode()
    batch_url = reverse(
        "importer_publikacji:batch-detail", kwargs={"batch_id": batch.pk}
    )
    assert batch_url in content
    assert "Wróć do paczki" in content


@pytest.mark.django_db
def test_cancel_returns_to_batch(client, operator):
    client.force_login(operator)
    batch = baker.make(MultipleWorksImport)
    session = baker.make(ImportSession, status=ImportSession.Status.VERIFIED)
    baker.make(MultipleWorksImportEntry, parent=batch, order=0, session=session)
    resp = client.post(
        reverse("importer_publikacji:cancel", kwargs={"session_id": session.pk})
    )
    batch_url = reverse(
        "importer_publikacji:batch-detail", kwargs={"batch_id": batch.pk}
    )
    # Redirect albo push-url na batch-detail:
    location = resp.get("Location") or resp.get("HX-Push-Url") or ""
    assert batch_url in location or batch_url in resp.content.decode()


@pytest.mark.django_db
def test_batch_detail_pending_entry_has_skip_action(client, operator):
    client.force_login(operator)
    batch = baker.make(MultipleWorksImport, provider_name="BibTeX")
    entry = baker.make(
        MultipleWorksImportEntry,
        parent=batch,
        order=0,
        session=None,
        skipped=False,
        parse_error="",
    )
    resp = client.get(
        reverse("importer_publikacji:batch-detail", kwargs={"batch_id": batch.pk})
    )
    assert resp.status_code == 200
    content = resp.content.decode()
    skip_url = reverse(
        "importer_publikacji:batch-entry-skip", kwargs={"entry_id": entry.pk}
    )
    import_url = reverse(
        "importer_publikacji:batch-entry-import", kwargs={"entry_id": entry.pk}
    )
    assert skip_url in content
    assert import_url in content


def test_bibtex_help_text_no_longer_says_first():
    provider = get_provider("BibTeX")
    assert "pierwszy" not in provider.input_help_text

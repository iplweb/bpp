"""PublicationImporter: rozdzielenie download (pobieranie) i process (import)."""

import pytest
from model_bakery import baker

from pbn_import.utils.publication_import import PublicationImporter


@pytest.fixture
def uczelnia(db):
    return baker.make("bpp.Uczelnia")


@pytest.fixture
def session(db, django_user_model):
    user = baker.make(django_user_model)
    return baker.make("pbn_import.ImportSession", user=user)


def _patch_setup(monkeypatch, importer_obj):
    """Pomiń realny setup — ustaw default_jednostka i zwróć uczelnię ze stepu."""
    importer_obj.default_jednostka = baker.make("bpp.Jednostka")
    monkeypatch.setattr(
        importer_obj,
        "_setup_uczelnia_and_jednostka",
        lambda *a, **k: importer_obj.uczelnia,
    )


def test_download_calls_only_download_helpers(session, uczelnia, monkeypatch):
    step = PublicationImporter(session, client=object(), uczelnia=uczelnia)
    _patch_setup(monkeypatch, step)
    called = []
    monkeypatch.setattr(
        step,
        "_download_publications",
        lambda *a, **k: called.append("dl") or None,
    )
    monkeypatch.setattr(
        step,
        "_download_publications_v2",
        lambda *a, **k: called.append("dl2") or None,
    )
    monkeypatch.setattr(
        step,
        "_import_publications",
        lambda *a, **k: called.append("import") or None,
    )
    step.download()
    assert called == ["dl", "dl2"]


def test_process_calls_only_import(session, uczelnia, monkeypatch):
    step = PublicationImporter(session, client=object(), uczelnia=uczelnia)
    _patch_setup(monkeypatch, step)
    called = []
    monkeypatch.setattr(
        step,
        "_download_publications",
        lambda *a, **k: called.append("dl") or None,
    )
    monkeypatch.setattr(
        step,
        "_import_publications",
        lambda *a, **k: called.append("import") or None,
    )
    step.process()
    assert called == ["import"]


def test_process_deletes_when_delete_existing(session, uczelnia, monkeypatch):
    step = PublicationImporter(
        session, client=object(), delete_existing=True, uczelnia=uczelnia
    )
    _patch_setup(monkeypatch, step)
    called = []
    monkeypatch.setattr(
        step,
        "_delete_existing_publications",
        lambda *a, **k: called.append("delete") or None,
    )
    monkeypatch.setattr(
        step,
        "_import_publications",
        lambda *a, **k: called.append("import") or None,
    )
    step.process()
    assert called == ["delete", "import"]

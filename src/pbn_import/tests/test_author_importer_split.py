"""AuthorImporter: download woła pobierz, process woła integruj."""

import pytest
from model_bakery import baker

from pbn_import.utils import author_import


@pytest.fixture
def uczelnia(db):
    return baker.make("bpp.Uczelnia", pbn_uid=baker.make("pbn_api.Institution"))


@pytest.fixture
def step(db, django_user_model, uczelnia):
    user = baker.make(django_user_model)
    session = baker.make("pbn_import.ImportSession", user=user)
    return author_import.AuthorImporter(session, client=object(), uczelnia=uczelnia)


def test_download_calls_pobierz_only(step, monkeypatch):
    called = []
    monkeypatch.setattr(
        author_import,
        "pobierz_ludzi_z_uczelni",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        author_import,
        "integruj_autorow_z_uczelni",
        lambda *a, **k: called.append("integruj"),
    )
    step.download()
    assert called == ["pobierz"]


def test_process_calls_integruj_only(step, monkeypatch):
    called = []
    monkeypatch.setattr(
        author_import,
        "pobierz_ludzi_z_uczelni",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        author_import,
        "integruj_autorow_z_uczelni",
        lambda *a, **k: called.append("integruj"),
    )
    step.process()
    assert called == ["integruj"]


def test_download_skips_without_pbn_uid(db, django_user_model, monkeypatch):
    uczelnia = baker.make("bpp.Uczelnia", pbn_uid=None)
    user = baker.make(django_user_model)
    session = baker.make("pbn_import.ImportSession", user=user)
    step = author_import.AuthorImporter(session, client=object(), uczelnia=uczelnia)
    called = []
    monkeypatch.setattr(
        author_import,
        "pobierz_ludzi_z_uczelni",
        lambda *a, **k: called.append("pobierz"),
    )
    result = step.download()
    assert called == []
    assert result["authors_imported"] is False

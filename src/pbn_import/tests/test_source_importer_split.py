"""SourceImporter: download woła pobierz, process woła importuj."""

import pytest
from model_bakery import baker

from pbn_import.utils import source_import


@pytest.fixture
def step(db, django_user_model):
    user = baker.make(django_user_model)
    session = baker.make("pbn_import.ImportSession", user=user)
    return source_import.SourceImporter(session, client=object())


def test_download_calls_pobierz_only(step, monkeypatch):
    called = []
    monkeypatch.setattr(
        source_import,
        "pobierz_zrodla_mnisw",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        source_import.importer,
        "importuj_zrodla",
        lambda *a, **k: called.append("importuj"),
    )
    step.download()
    assert called == ["pobierz"]


def test_process_calls_importuj_only(step, monkeypatch):
    called = []
    monkeypatch.setattr(
        source_import,
        "pobierz_zrodla_mnisw",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        source_import.importer,
        "importuj_zrodla",
        lambda *a, **k: called.append("importuj") or 5,
    )
    step.process()
    assert called == ["importuj"]

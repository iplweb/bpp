"""PublisherImporter: download woła pobierz, process woła importuj."""

import pytest
from model_bakery import baker

from pbn_import.utils import publisher_import


@pytest.fixture
def step(db, django_user_model):
    user = baker.make(django_user_model)
    session = baker.make("pbn_import.ImportSession", user=user)
    return publisher_import.PublisherImporter(session, client=object())


def test_download_calls_pobierz_only(step, monkeypatch):
    called = []
    monkeypatch.setattr(
        publisher_import,
        "pobierz_wydawcow_mnisw",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        publisher_import.importer,
        "importuj_wydawcow",
        lambda *a, **k: called.append("importuj"),
    )
    step.download()
    assert called == ["pobierz"]


def test_process_calls_importuj_only(step, monkeypatch):
    called = []
    monkeypatch.setattr(
        publisher_import,
        "pobierz_wydawcow_mnisw",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        publisher_import.importer,
        "importuj_wydawcow",
        lambda *a, **k: called.append("importuj") or 7,
    )
    step.process()
    assert called == ["importuj"]

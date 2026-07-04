"""ConferenceImporter: download woła pobierz, process woła integruj."""

import pytest
from model_bakery import baker

from pbn_import.utils import conference_import


@pytest.fixture
def step(db, django_user_model):
    user = baker.make(django_user_model)
    session = baker.make("pbn_import.ImportSession", user=user)
    return conference_import.ConferenceImporter(session, client=object())


def test_download_calls_pobierz_not_integruj(step, monkeypatch):
    called = []
    monkeypatch.setattr(
        conference_import,
        "pobierz_konferencje",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        conference_import,
        "integruj_konferencje",
        lambda *a, **k: called.append("integruj"),
    )
    step.download()
    assert called == ["pobierz"]


def test_process_calls_integruj_not_pobierz(step, monkeypatch):
    called = []
    monkeypatch.setattr(
        conference_import,
        "pobierz_konferencje",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        conference_import,
        "integruj_konferencje",
        lambda *a, **k: called.append("integruj") or 3,
    )
    step.process()
    assert called == ["integruj"]


def test_process_warns_when_mirror_empty(step, monkeypatch):
    monkeypatch.setattr(conference_import, "integruj_konferencje", lambda *a, **k: 0)
    step.process()
    warnings = step.session.logs.filter(level="warning")
    assert warnings.exists()

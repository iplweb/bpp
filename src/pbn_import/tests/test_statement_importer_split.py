"""StatementImporter: download = pobierz oświadczenia, process = integracja."""

import pytest
from model_bakery import baker

from pbn_import.utils import statement_import
from pbn_import.utils.statement_import import StatementImporter


@pytest.fixture
def uczelnia(db):
    return baker.make("bpp.Uczelnia")


@pytest.fixture
def session(db, django_user_model):
    user = baker.make(django_user_model)
    return baker.make("pbn_import.ImportSession", user=user)


def test_download_calls_only_pobierz_oswiadczenia(session, uczelnia, monkeypatch):
    step = StatementImporter(session, client=object(), uczelnia=uczelnia)
    called = []
    monkeypatch.setattr(
        statement_import,
        "pobierz_oswiadczenia_z_instytucji",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        statement_import,
        "integruj_oswiadczenia_z_instytucji",
        lambda *a, **k: called.append("integruj"),
    )
    step.download()
    assert called == ["pobierz"]


def test_process_integrates_without_redownloading_statements(
    session, uczelnia, monkeypatch
):
    step = StatementImporter(session, client=object(), uczelnia=uczelnia)
    called = []
    monkeypatch.setattr(
        statement_import,
        "pobierz_oswiadczenia_z_instytucji",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        statement_import,
        "integruj_oswiadczenia_z_instytucji",
        lambda *a, **k: called.append("integruj"),
    )
    monkeypatch.setattr(
        step.publication_importer,
        "_setup_uczelnia_and_jednostka",
        lambda *a, **k: uczelnia,
    )
    step.publication_importer.default_jednostka = baker.make("bpp.Jednostka")
    monkeypatch.setattr(step, "_download_missing_publications", lambda *a, **k: None)
    step.process()
    assert called == ["integruj"]

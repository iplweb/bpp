"""Testy dyspozytora faz w ImportStepBase (download/process/run/__call__)."""

import pytest
from model_bakery import baker

from pbn_import.utils.base import ImportStepBase


class _DummyStep(ImportStepBase):
    step_name = "dummy"
    step_description = "Dummy"

    def __init__(self, session):
        super().__init__(session)
        self.calls = []

    def download(self):
        self.calls.append("download")
        return {"phase": "download"}

    def process(self):
        self.calls.append("process")
        return {"phase": "process"}


@pytest.fixture
def session(db, django_user_model):
    user = baker.make(django_user_model)
    return baker.make("pbn_import.ImportSession", user=user)


def test_call_default_runs_both_phases(session):
    step = _DummyStep(session)
    result = step()  # default method="run"
    assert step.calls == ["download", "process"]
    assert result == {"phase": "process"}


def test_call_download_only(session):
    step = _DummyStep(session)
    result = step(method="download")
    assert step.calls == ["download"]
    assert result == {"phase": "download"}


def test_call_process_only(session):
    step = _DummyStep(session)
    result = step(method="process")
    assert step.calls == ["process"]
    assert result == {"phase": "process"}


def test_base_download_process_not_implemented(session):
    class _Bare(ImportStepBase):
        step_name = "bare"

    bare = _Bare(session)
    with pytest.raises(NotImplementedError):
        bare.download()
    with pytest.raises(NotImplementedError):
        bare.process()

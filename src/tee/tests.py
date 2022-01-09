from io import StringIO

import pytest
from django.core.management import call_command

from tee.models import Log


@pytest.fixture
def stdout():
    return StringIO()


@pytest.fixture
def stderr():
    return StringIO()


@pytest.mark.django_db
def test_tee_okay(stdout: StringIO, stderr: StringIO, mocker):
    with mocker.patch("django.db.connections.close_all"):
        # patch wymagany, bo BaseCommand wywołuje close_all
        call_command("tee", "tee_test_okay", stdout=stdout, stderr=stderr)
    assert Log.objects.first().finished_successfully
    assert "Used print()" in stdout.getvalue()
    assert "Used print()" in stderr.getvalue()


@pytest.mark.django_db
def test_tee_exception(stdout, stderr, mocker):
    with mocker.patch("django.db.connections.close_all"):
        # patch wymagany, bo BaseCommand wywołuje close_all
        call_command("tee", "tee_test_exception", stdout=stdout, stderr=stderr)
    assert Log.objects.first().traceback

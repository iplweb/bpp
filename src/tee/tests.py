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
def test_tee_okay(stdout: StringIO, stderr: StringIO):
    call_command("tee", "tee_test_okay", stdout=stdout, stderr=stderr)
    assert Log.objects.first().exit_code == 0
    assert "Used print()" in stdout.getvalue()
    assert "Used print()" in stderr.getvalue()


@pytest.mark.django_db
def test_tee_exception(stdout, stderr):
    call_command("tee", "tee_test_exception", stdout=stdout, stderr=stderr)
    assert Log.objects.first().traceback


@pytest.mark.django_db
def test_tee_result(stdout, stderr):
    call_command("tee", "tee_test_result", stdout=stdout, stderr=stderr)
    assert "Unable to encode" in Log.objects.first().exit_value

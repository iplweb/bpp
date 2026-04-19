from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from model_bakery import baker

from tee.models import Log


@pytest.fixture
def stdout():
    return StringIO()


@pytest.fixture
def stderr():
    return StringIO()


@pytest.mark.django_db
def test_tee_okay(stdout: StringIO, stderr: StringIO, mocker):
    # patch wymagany, bo BaseCommand wywołuje close_all
    mocker.patch("django.db.connections.close_all")
    call_command("tee", "tee_test_okay", stdout=stdout, stderr=stderr)
    assert Log.objects.first().finished_successfully
    assert "Used print()" in stdout.getvalue()
    assert "Used print()" in stderr.getvalue()


@pytest.mark.django_db
def test_tee_exception(stdout, stderr, mocker):
    # patch wymagany, bo BaseCommand wywołuje close_all
    mocker.patch("django.db.connections.close_all")
    call_command("tee", "tee_test_exception", stdout=stdout, stderr=stderr)
    assert Log.objects.first().traceback


@pytest.mark.django_db
def test_admin_view(admin_client):
    """Visit 'changelist' and 'details' page for Log model"""

    model = Log

    baker.make(Log)

    app_label = "tee"
    model_name = "log"

    url_name = f"admin:{app_label}_{model_name}_changelist"
    url = reverse(url_name)

    res = admin_client.get(url)
    assert res.status_code == 200, f"changelist failed for {model!r}"

    res = admin_client.get(url + "?q=fafa")
    assert res.status_code == 200, f"changelist query failed for {model!r}"

    url_name = f"admin:{app_label}_{model_name}_add"
    url = reverse(url_name)
    res = admin_client.get(url)
    assert res.status_code == 403

import pytest
from django.db import connection
from model_bakery import baker

from long_running.models import Report
from test_bpp.models import TestOperation


@pytest.fixture
def operation(admin_user):
    return TestOperation.objects.create(owner=admin_user)


@pytest.fixture
def report(db):
    class TestReport(Report):
        sent_notifications = []

        def send_notification(self, *args, **kw):
            self.sent_notifications.append((args, kw))

    # Create the schema for our test model
    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(TestReport)

    yield baker.make(TestReport)

    # with connection.schema_editor() as schema_editor:
    #     schema_editor.delete_model(TestReport)

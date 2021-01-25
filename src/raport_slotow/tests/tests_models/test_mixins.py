import sys

import pytest
from django.db import connection
from model_mommy import mommy

from raport_slotow.models.mixins import Report


@pytest.fixture
def report(db):
    class TestReport(Report):
        sent_notifications = []

        def send_notification(self, *args, **kw):
            self.sent_notifications.append((args, kw))

    # Create the schema for our test model
    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(TestReport)

    yield mommy.make(TestReport)

    # with connection.schema_editor() as schema_editor:
    #     schema_editor.delete_model(TestReport)


def test_Report_various(report):
    report.create_report = lambda self: True

    report.mark_started()
    report.mark_finished_okay()
    try:
        raise NotImplementedError
    except BaseException:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        report.mark_finished_with_error(exc_type, exc_value, exc_traceback)


def test_Report_task_create_report_good(report):
    report.create_report = lambda: True
    report.task_create_report()
    report.refresh_from_db()
    assert report.finished_successfully


def test_Report_task_create_report_bad(report):
    def bad_fun():
        raise ValueError("xxx")

    report.create_report = lambda: bad_fun()
    report.task_create_report(raise_exceptions=False)
    report.refresh_from_db()
    assert not report.finished_successfully
    assert "xxx" in report.traceback

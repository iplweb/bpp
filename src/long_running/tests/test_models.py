import sys

import pytest
from django.utils import timezone

from long_running import const


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


def test_Operation_readable_exception(operation):
    assert operation.readable_exception() is None

    operation.traceback = "1\n2\n3"
    assert operation.readable_exception() == "3"


def test_Operation_mark_reset(operation):
    operation.mark_reset()
    assert True


def test_Operation_on_finished_with_error(operation):
    operation.on_finished_with_error()
    assert True


def test_Operation_perform(operation):
    with pytest.raises(NotImplementedError):
        operation.perform()


def test_Operation_get_redirect_prefix(operation):
    assert operation.get_redirect_prefix() == "test_bpp:testoperation"


def test_Operation_get_url(operation, mocker):
    rev = mocker.patch("long_running.models.reverse")
    operation.get_url("foo")
    rev.assert_called_once()


def test_Operation_get_state(operation):
    assert operation.get_state() == const.PROCESSING_NOT_STARTED
    operation.started_on = timezone.now()
    assert operation.get_state() == const.PROCESSING_STARTED
    operation.finished_on = timezone.now()
    operation.finished_successfully = False
    assert operation.get_state() == const.PROCESSING_FINISHED_WITH_ERROR
    operation.finished_successfully = True
    assert operation.get_state() == const.PROCESSING_FINISHED_SUCCESSFULLY

    operation.started_on = None
    assert operation.get_state() == const.PROCESSING_NOT_STARTED

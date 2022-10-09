import pytest

from long_running.exceptions import (
    ObjectDoesNotExistException,
    ProcessingAlreadyStartedException,
)
from long_running.tasks import perform_generic_long_running_task

from django.utils import timezone


@pytest.mark.django_db
def test_perform_generic_long_running_task_no_tries_max_tries(wydawnictwo_ciagle):

    with pytest.raises(
        ObjectDoesNotExistException,
    ):
        perform_generic_long_running_task.delay(
            "bpp", "wydawnictwo_ciagle", wydawnictwo_ciagle.pk, no_tries=20, max_tries=1
        )


@pytest.mark.django_db
def test_perform_generic_long_running_task_DoesNotExist(mocker):
    perform_generic_long_running_task.apply_async = mocker.MagicMock()
    perform_generic_long_running_task("test_bpp", "testobjectthatdoesnotexist", 1)
    perform_generic_long_running_task.apply_async.assert_called_once()


def test_perform_generic_long_running_task(operation):
    operation.started_on = timezone.now()
    operation.save()

    with pytest.raises(ProcessingAlreadyStartedException):
        perform_generic_long_running_task("test_bpp", "testoperation", operation.pk)

    operation.started_on = None
    operation.save()

    with pytest.raises(
        NotImplementedError,
    ):
        perform_generic_long_running_task("test_bpp", "testoperation", operation.pk)


def test_Operation_redirect_prefix(operation):
    operation.redirect_prefix = "foo"
    assert operation.get_redirect_prefix() == "foo"


def test_Operation_on_finished_with_error(operation, mocker):
    operation.send_notification = mocker.MagicMock()
    operation.on_finished_with_error()
    operation.send_notification.assert_called_once()

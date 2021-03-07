import pytest

from long_running.tasks import perform_generic_long_running_task


def test_perform_generic_long_running_task(wydawnictwo_ciagle):

    with pytest.raises(
        AttributeError,
        match="object has no attribute 'task_perform'",
    ):
        perform_generic_long_running_task.delay(
            "bpp", "wydawnictwo_ciagle", wydawnictwo_ciagle.pk
        )

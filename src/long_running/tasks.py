from django.contrib.contenttypes.models import ContentType

from django_bpp.celery_tasks import app
from long_running.exceptions import (
    ObjectDoesNotExistException,
    ProcessingAlreadyStartedException,
)


@app.task
def perform_generic_long_running_task(
    app_label, model, pk, no_tries=0, max_tries=10, delay_between_tries=5
):

    if no_tries >= max_tries:
        raise ObjectDoesNotExistException(app_label, model, pk, no_tries, max_tries)

    ct = ContentType.objects.get_by_natural_key(app_label, model)
    klass = ct.model_class()

    try:
        obj = klass.objects.get(pk=pk)
    except klass.DoesNotExist:
        # retry this task with `delay_between_tries` into the future
        return perform_generic_long_running_task.apply_async(
            args=(app_label, model, pk, no_tries + 1, max_tries, delay_between_tries),
            countdown=delay_between_tries,
        )

    if obj.started_on is not None:
        raise ProcessingAlreadyStartedException(obj)

    obj.task_perform()

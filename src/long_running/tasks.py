from django.contrib.contenttypes.models import ContentType

from django_bpp.celery_tasks import app
from long_running.util import wait_for_object


@app.task
def perform_generic_long_running_task(app_label, model, pk):
    ct = ContentType.objects.get_by_natural_key(app_label, model)
    klass = ct.model_class()
    o = wait_for_object(klass, pk)
    o.task_perform()

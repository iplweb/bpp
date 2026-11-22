from django.apps import apps

from bpp.zglaszanie_bledow import capture_exception
from django_bpp.celery_tasks import app
from dspace_api.eksport import eksportuj_rekord


@app.task
def queue_dspace_export_batch(app_label, model_name, record_ids, user_id=None):
    model = apps.get_model(app_label, model_name)
    for rec in model.objects.filter(id__in=record_ids):
        try:
            eksportuj_rekord(rec)
        except Exception:
            capture_exception()
            raise

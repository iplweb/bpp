import traceback

from celery.utils.log import get_task_logger
from django.db import transaction
from django.urls import reverse

import notifications
from django_bpp.celery_tasks import app
from import_dyscyplin.models import Import_Dyscyplin
from notifications.models import Notification

logger = get_task_logger("django")


@app.task(bind=True)
def stworz_kolumny(self, pk):
    self.update_state(state="RUNNING")
    i = Import_Dyscyplin.objects.get(pk=pk)

    try:
        with transaction.atomic():
            Import_Dyscyplin.objects.select_for_update().filter(pk=pk)
            try:
                i.stworz_kolumny()
            except Exception:
                logger.exception("Podczas tworzenia kolumn")
                i.info = traceback.format_exc()
            finally:
                i.save(update_fields=["stan", "modified", "info"])
    finally:
        i = Import_Dyscyplin.objects.get(pk=pk)
        self.update_state(state="DONE")
        i.task_id = None
        i.save()

        Notification.objects.send_redirect(
            i, "%s?notification=1" % reverse("import_dyscyplin:detail", args=(i.pk,)),
        )


@app.task(bind=True)
def przeanalizuj_import_dyscyplin(self, pk):
    self.update_state(state="RUNNING")
    i = Import_Dyscyplin.objects.get(pk=pk)

    try:
        with transaction.atomic():
            Import_Dyscyplin.objects.select_for_update().filter(pk=pk)
            try:
                i.przeanalizuj()
                i.integruj_dyscypliny()
                i.sprawdz_czy_poprawne()
                i.sprawdz_czy_konieczne()
            except Exception:
                logger.exception("Podczas analizy pliku")
                i.info = traceback.format_exc()
            finally:
                i.save(update_fields=["stan", "modified", "info"])
    finally:
        # Odśwież obiekt, bo być może web_page_uid się zmieniło
        # i.refresh_from_db() nie zadziała, bo django-fsm zablokuje bezpośrednią
        # modyfukację pola 'status'
        i = Import_Dyscyplin.objects.get(pk=pk)
        self.update_state(state="DONE")

        i.task_id = None
        i.save()

        Notification.objects.send_redirect(
            i, "%s?notification=1" % reverse("import_dyscyplin:detail", args=(i.pk,)),
        )


@app.task(bind=True)
def integruj_import_dyscyplin(self, pk):
    self.update_state(state="RUNNING")
    i = Import_Dyscyplin.objects.get(pk=pk)

    try:
        with transaction.atomic():
            Import_Dyscyplin.objects.select_for_update().filter(pk=pk)
            try:
                i.integruj_wiersze()
            except Exception:
                logger.exception("Podczas integracji wierszy")
                i.info = traceback.format_exc()
            finally:
                i.save(update_fields=["stan", "modified", "info"])

    finally:
        i = Import_Dyscyplin.objects.get(pk=pk)
        self.update_state(state="DONE")
        i.task_id = None
        i.save()

        Notification.objects.send_redirect(
            i, "%s?notification=1" % reverse("import_dyscyplin:detail", args=(i.pk,)),
        )

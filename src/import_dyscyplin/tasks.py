from celery.utils.log import get_task_logger
from django.urls import reverse

import notifications
from django_bpp.celery_tasks import app
from import_dyscyplin.models import Import_Dyscyplin

logger = get_task_logger(__name__)

@app.task
def przeanalizuj_import_dyscyplin(pk):
    i = Import_Dyscyplin.objects.get(pk=pk)
    try:
        try:
            i.przeanalizuj()
        except Exception as e:
            logger.exception("Podczas analizy pliku")
            i.info = str(e)

        i.save()

    finally:
        # Niezależnie od sytuacji uruchom powiadamianie. Jeżeli wystąpi
        # błąd, to tez pojawi się o tym informacja na UI
        res = notifications.send_redirect(
            i.owner.username,
            "%s?notification=1" % reverse("import_dyscyplin:detail", args=(i.pk,)),
            i.web_page_uid,
        )

        if res.status_code == 200:
            # no_reached = res.json()['subscribers']

            # Zmienna no_reached zawiera ilość osób, do których została faktycznie
            # dostarczona wiadomość przekierowania na stronę WWW. W przyszłości
            # można wykorzystać tą liczbę, aby w razie, gdy nikt tej wiadomości nie
            # słuchał i nie odebrał, wysłąć np. maila lub inny rodzaj powiadomienia.
            pass


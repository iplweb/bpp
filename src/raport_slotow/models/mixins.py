import sys
import traceback
import uuid

from django.conf import settings
from django.contrib.messages import constants
from django.db import models, transaction
from django.utils import timezone

TRACEBACK_LENGTH_LIMIT = 65535


class NullNotificationMixin:
    def send_notification(self, msg, level=None):
        return


class Report(NullNotificationMixin, models.Model):
    """Długo działający raport"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    created_on = models.DateTimeField(auto_now_add=True)
    last_updated_on = models.DateTimeField(auto_now=True)

    started_on = models.DateTimeField(null=True, blank=True)
    finished_on = models.DateTimeField(null=True, blank=True)

    finished_successfully = models.BooleanField(default=False)
    traceback = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["-last_updated_on"]
        abstract = True

    def mark_started(self):
        # uruchamiać POZA transakcją

        self.started_on = timezone.now()
        self.save()
        self.send_notification(
            f"Rozpoczęto przetwarzanie, {self.started_on}", constants.INFO
        )

    def mark_finished_okay(self):
        # uruchamiać POZA transakcją
        self.finished_successfully = True
        self.finished_on = timezone.now()
        self.save()
        self.send_notification(
            f"Zakończono przetwarzanie - wszystko OK, {self.started_on}",
            constants.SUCCESS,
        )

    def mark_finished_with_error(self, exc_type, exc_value, exc_traceback):
        # uruchamiać POZA transakcją
        self.finished_successfully = False
        self.finished_on = timezone.now()
        self.traceback = "\n".join(
            traceback.format_exception(
                exc_type, exc_value, exc_traceback, limit=TRACEBACK_LENGTH_LIMIT
            )
        )
        self.save()
        self.send_notification(
            f"Zakończono z błędem, {self.finished_on}", constants.ERROR
        )

    def on_finished_successfully(self):
        pass

    def task_create_report(self, raise_exceptions=True):
        """Runs a function in context of curret report, which means: it sets
        the variables according to success or failure of a given function.
        """
        # uruchamiać POZA transakcją
        # uruchamiać z poziomu zadań celery
        self.mark_started()
        try:
            with transaction.atomic():
                self.create_report()
                self.mark_finished_okay()
            self.on_finished_successfully()
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.mark_finished_with_error(exc_type, exc_value, exc_traceback)
            if raise_exceptions:
                raise exc_value.with_traceback(exc_traceback)

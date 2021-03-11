import sys
import traceback
import uuid

from django.conf import settings
from django.contrib.messages import constants
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone

from long_running import const
from long_running.notification_mixins import NullNotificationMixin

TRACEBACK_LENGTH_LIMIT = 65535


class Operation(NullNotificationMixin, models.Model):
    """Długo działająca operacja"""

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

    def readable_exception(self):
        if self.traceback is None:
            return
        return [line for line in self.traceback.split("\n") if line][-1]

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

    @transaction.atomic
    def mark_reset(self):
        """Prepares the report for re-generation"""
        self.started_on = None
        self.finished_on = None
        self.finished_successfully = False
        self.traceback = None
        self.on_reset()
        self.save()

    def on_finished_successfully(self):
        pass

    def on_finished_with_error(self):
        self.send_notification(
            f"Zakończono z błędem, {self.finished_on}", constants.ERROR
        )

    def on_finished(self):
        self.send_processing_finished()

    def on_reset(self):
        pass

    def perform(self):
        raise NotImplementedError("Override this in a subclass.")

    def task_perform(self, raise_exceptions=True):
        """Runs a function in context of curret report, which means: it sets
        the variables according to success or failure of a given function.

        This function is meant to be called outside of a transaction,
        from a celery worker - only.
        """
        self.mark_started()
        try:
            with transaction.atomic():
                self.perform()
                self.mark_finished_okay()
            self.on_finished_successfully()
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.mark_finished_with_error(exc_type, exc_value, exc_traceback)
            self.on_finished_with_error()
            if raise_exceptions:
                raise exc_value.with_traceback(exc_traceback)
        finally:
            self.on_finished()

    redirect_prefix = None

    def get_redirect_prefix(self):
        """
        LongRunningOperationRouterView to widok, który decyduje, co zrobić z daną operacją.
        W tym celu korzysta z redirect_prefix czyli początku URLa, który domyślnie
        wygląda jak aplikacja+nazwa obiektu, czyli np:

            import_czegostam:importosob

        Do takiego redirect_prefix dodajemy suffix czyli np. -router, -details, -results
        i w ten sposob odsyłamy użytkownika na odpowiednią stronę - bądź to z monitorowaniem
        postępu danej operacji, bądź to z wynikami operacji.

        Domyślnie należy użytkownika odesłać na suffix -router, który to już
        potem decyduje, gdzie dalej odesłać przeglądarkę.
        """
        if self.redirect_prefix:
            return self.redirect_prefix
        return f"{self._meta.app_label}:{self._meta.model_name}"

    def get_url(self, suffix):
        return reverse(f"{self.get_redirect_prefix()}-{suffix}", args=(self.pk,))

    def get_absolute_url(self):
        return self.get_url("router")

    def get_state(self):
        if self.started_on is None:
            return const.PROCESSING_NOT_STARTED

        if self.started_on is not None and self.finished_on is None:
            return const.PROCESSING_STARTED

        if self.started_on is not None and self.finished_on is not None:
            if self.finished_successfully:
                return const.PROCESSING_FINISHED_SUCCESSFULLY
            return const.PROCESSING_FINISHED_WITH_ERROR

        raise NotImplementedError("This line should never execute")


class Report(Operation):
    def perform(self):
        self.create_report()

    def task_create_report(self, raise_exceptions=True):
        return self.task_perform(raise_exceptions=raise_exceptions)

    class Meta:
        abstract = True

# -*- encoding: utf-8 -*-
import uuid
from datetime import datetime
import traceback
import sys

from django.conf import settings
from django.db import models
from django.db.models import CASCADE, UUIDField
# from django_extensions.db.fields import UUIDField
from django_extensions.db.fields.json import JSONField
from django.utils.translation import gettext_lazy as _
from zope.interface import classImplements

from celeryui import interfaces
from celeryui.interfaces import IReportMaker, IWebTask


TRACEBACK_MAX_LENGTH = 10240

REPORTS_PATH = 'report'


class Status:
    COMPLETED = _("completed")
    ERROR = _("error")
    IN_PROGRESS = _("in progress")
    WAITING = _("waiting")


class Report(models.Model):
    uid = UUIDField(unique=True, editable=False, blank=True, default=uuid.uuid4)

    function = models.TextField()
    arguments = JSONField(null=True, blank=True)

    ordered_by = models.ForeignKey(settings.AUTH_USER_MODEL, CASCADE)
    ordered_on = models.DateTimeField(auto_now_add=True)

    file = models.FileField(upload_to=REPORTS_PATH, null=True, blank=True)

    started_on = models.DateTimeField(null=True, blank=True)
    finished_on = models.DateTimeField(null=True, blank=True)

    # Progress in percent
    progress = models.FloatField(null=True, blank=True, default=0.0)

    error = models.BooleanField(default=False)
    traceback = models.TextField(
        max_length=TRACEBACK_MAX_LENGTH, null=True, blank=True)

    class Meta:
        ordering = ['-ordered_on']

    def status(self):
        if self.started_on is None:
            return Status.WAITING

        if self.finished_on is None:
            return Status.IN_PROGRESS

        if self.error:
            return Status.ERROR

        return Status.COMPLETED

    def started(self):
        self.started_on = datetime.now()
        self.progress = 0.0
        self.save()

    def finished_okay(self):
        """This report has been completed, mark it as finished.
        """
        self.finished_on = datetime.now()
        self.progress = 1.0
        self.save()

    def finished_with_error(self, exc_type, exc_value, exc_traceback):
        self.finished_on = datetime.now()
        self.error = True
        self.traceback = "\n".join(traceback.format_exception(
            exc_type, exc_value, exc_traceback, limit=TRACEBACK_MAX_LENGTH))
        self.save()

    def run_in_context(self, function, raise_exceptions=False):
        """Runs a function in context of curret report, which means: it sets
        the variables according to success or failure of a given function.
        """
        try:
            function()
            self.finished_okay()
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            self.finished_with_error(exc_type, exc_value, exc_traceback)
            if raise_exceptions:
                raise exc_value.with_traceback(exc_traceback)

    def execute(self, raise_exceptions=False):
        self.run_in_context(
            IReportMaker(self).perform,
            raise_exceptions=raise_exceptions)

    def adapted(self):
        """Used as helper function in templates"""
        return IWebTask(self)

classImplements(Report, interfaces.IReport)

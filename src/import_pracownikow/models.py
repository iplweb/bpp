from django.db import models

# Create your models here.
from long_running.asgi_notification_mixin import ASGINotificationMixin
from long_running.models import Operation


class ImportPracownikow(ASGINotificationMixin, Operation):
    plik_xls = models.FileField()

    def perform(self):
        raise NotImplementedError

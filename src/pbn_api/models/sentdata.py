from django.db import models

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import JSONField


class SentDataManager(models.Manager):
    def get_for_rec(self, rec):
        return self.get(
            object_id=rec.pk, content_type=ContentType.objects.get_for_model(rec)
        )

    def check_if_needed(self, rec, data: dict):
        try:
            sd = self.get_for_rec(rec)
        except SentData.DoesNotExist:
            return True

        if sd.data_sent != data:
            return True

        if not sd.uploaded_okay:
            return True

        return False

    def updated(self, rec, data: dict, uploaded_okay=True, exception=None):
        try:
            sd = self.get_for_rec(rec)
        except SentData.DoesNotExist:
            self.create(
                object=rec,
                data_sent=data,
                uploaded_okay=uploaded_okay,
                exception=exception,
            )
            return

        sd.data_sent = data
        sd.uploaded_okay = uploaded_okay
        sd.exception = exception
        sd.save()


class SentData(models.Model):
    content_type = models.ForeignKey(
        "contenttypes.ContentType", on_delete=models.CASCADE
    )
    object_id = models.PositiveIntegerField(db_index=True)

    object = GenericForeignKey()

    data_sent = JSONField("Wysłane dane")
    last_updated_on = models.DateTimeField("Data operacji", auto_now=True)

    uploaded_okay = models.BooleanField(
        "Wysłano poprawnie", default=True, db_index=True
    )
    exception = models.TextField("Kod błędu", max_length=65535, blank=True, null=True)

    objects = SentDataManager()

    class Meta:
        verbose_name = "Informacja o wysłanych danych"
        verbose_name_plural = "Informacje o wysłanych danych"

    object.verbose_name = "Rekord"

    def __str__(self):
        return (
            f"Informacja o wysłanych do PBN danych dla rekordu ({self.content_type_id},{self.object_id}) "
            f"z dnia {self.last_updated_on} (status: {'OK' if self.uploaded_okay else 'ERR'})"
        )

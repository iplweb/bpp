from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import JSONField
from django.utils import timezone


class SentToDSpaceManager(models.Manager):
    def get_for_rec(self, rec, uczelnia):
        return self.get(
            object_id=rec.pk,
            content_type=ContentType.objects.get_for_model(rec),
            uczelnia=uczelnia,
        )

    def check_if_upload_needed(self, rec, uczelnia, data: dict):
        try:
            sd = self.get_for_rec(rec, uczelnia)
            if sd.data_sent == data and sd.submitted_successfully:
                return False
        except SentToDSpace.DoesNotExist:
            pass
        return True

    def create_or_update_before_upload(self, rec, uczelnia, data: dict):
        try:
            sd = self.get_for_rec(rec, uczelnia)
            sd.submitted_successfully = False
            sd.submitted_at = timezone.now()
            sd.api_response_status = ""
            sd.exception = ""
            sd.data_sent = data
            sd.save()
            return sd
        except SentToDSpace.DoesNotExist:
            return self.create(
                object=rec,
                uczelnia=uczelnia,
                data_sent=data,
                submitted_successfully=False,
                submitted_at=timezone.now(),
            )

    def mark_as_successful(
        self, rec, uczelnia, dspace_uuid=None, api_response_status=""
    ):
        sd = self.get_for_rec(rec, uczelnia)
        sd.submitted_successfully = True
        sd.dspace_uuid = dspace_uuid
        sd.api_response_status = api_response_status
        sd.exception = ""
        sd.save()

    def mark_as_failed(self, rec, uczelnia, exception="", api_response_status=""):
        sd = self.get_for_rec(rec, uczelnia)
        sd.submitted_successfully = False
        sd.exception = str(exception) if exception else ""
        sd.api_response_status = api_response_status
        sd.save()


class SentToDSpace(models.Model):
    content_type = models.ForeignKey(
        "contenttypes.ContentType", on_delete=models.CASCADE
    )
    object_id = models.PositiveIntegerField(db_index=True)
    object = GenericForeignKey()

    uczelnia = models.ForeignKey("bpp.Uczelnia", on_delete=models.CASCADE)

    dspace_uuid = models.UUIDField(
        "UUID itemu w DSpace", null=True, blank=True
    )
    data_sent = JSONField("Wysłane dane")
    submitted_successfully = models.BooleanField(
        "Wysłano pomyślnie", default=False, db_index=True
    )
    submitted_at = models.DateTimeField("Data wysyłki", null=True, blank=True)
    exception = models.TextField("Kod błędu", blank=True, default="")
    api_response_status = models.TextField(
        "Status odpowiedzi API", blank=True, default=""
    )
    last_updated_on = models.DateTimeField("Data operacji", auto_now=True)

    objects = SentToDSpaceManager()

    class Meta:
        verbose_name = "Informacja o wysłaniu do DSpace"
        verbose_name_plural = "Informacje o wysłaniu do DSpace"
        unique_together = (("content_type", "object_id", "uczelnia"),)

    def __str__(self):
        status = "OK" if self.submitted_successfully else "ERR"
        return (
            f"DSpace[{self.uczelnia_id}] rekord "
            f"({self.content_type_id},{self.object_id}) — {status}"
        )

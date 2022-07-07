from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import JSONField

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from bpp import const
from bpp.models import LinkDoPBNMixin


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

    def updated(
        self, rec, data: dict, pbn_uid_id=None, uploaded_okay=True, exception=None
    ):
        try:
            sd = self.get_for_rec(rec)
        except SentData.DoesNotExist:
            self.create(
                object=rec,
                data_sent=data,
                uploaded_okay=uploaded_okay,
                pbn_uid_id=pbn_uid_id,
                exception=exception,
            )
            return

        sd.data_sent = data
        sd.uploaded_okay = uploaded_okay
        sd.exception = exception
        sd.pbn_uid_id = pbn_uid_id
        sd.save()

    def ids_for_model(self, model):
        return self.filter(content_type=ContentType.objects.get_for_model(model))

    def bad_uploads(self, model):
        return (
            self.ids_for_model(model)
            .filter(uploaded_okay=False)
            .values_list("object_id", flat=True)
            .distinct()
        )


class SentData(LinkDoPBNMixin, models.Model):
    url_do_pbn = const.LINK_PBN_DO_PUBLIKACJI
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

    pbn_uid = models.ForeignKey(
        "pbn_api.Publication",
        verbose_name="Publikacja z PBN",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )

    typ_rekordu = models.CharField(max_length=50, blank=True, null=True)

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

    def link_do_pbn_wartosc_id(self):
        return self.pbn_uid_id

    def rekord_w_bpp(self):
        try:
            return self.object
        except ObjectDoesNotExist:
            pass

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):

        if update_fields and "data_sent" in update_fields:
            if self.typ_rekordu != self.data_sent.get("type"):
                update_fields.append("typ_rekordu")

        self.typ_rekordu = self.data_sent.get("type")
        return super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

import os
import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django_softdelete.models import SoftDeleteModel
from model_utils import Choices

from bpp.const import TRYB_DOSTEPU


def element_repozytorium_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"protected/repozytorium/{uuid.uuid4()}{ext}"


class Element_Repozytorium(SoftDeleteModel):
    ER_TRYB_DOSTEPU = Choices(
        (TRYB_DOSTEPU.NIEJAWNY, "niejawny"),
        (TRYB_DOSTEPU.TYLKO_W_SIECI, "tylko w sieci"),
        (TRYB_DOSTEPU.JAWNY, "jawny"),
    )

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()

    rekord = GenericForeignKey("content_type", "object_id")

    rodzaj = models.CharField(max_length=200)
    nazwa_pliku = models.CharField(max_length=200)
    tryb_dostepu = models.PositiveSmallIntegerField(choices=ER_TRYB_DOSTEPU)
    plik = models.FileField(
        "Plik",
        upload_to=element_repozytorium_upload_to,
        max_length=765,
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = "element repozytorium"
        verbose_name_plural = "elementy repozytorium"

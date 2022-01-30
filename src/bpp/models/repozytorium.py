from django.db import models
from model_utils import Choices

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from bpp.const import TRYB_DOSTEPU


class Element_Repozytorium(models.Model):
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

    class Meta:
        verbose_name = "element repozytorium"
        verbose_name_plural = "elementy repozytorium"

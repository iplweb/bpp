from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import CASCADE


class Grant(models.Model):
    nazwa_projektu = models.TextField(blank=True, null=True)
    zrodlo_finansowania = models.TextField(blank=True, null=True)
    numer_projektu = models.CharField(max_length=200, unique=True)
    rok = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "grant"
        verbose_name_plural = "granty"

    def __str__(self):
        return f"{self.numer_projektu} {self.nazwa_projektu or ''}".strip()


class Grant_Rekordu(models.Model):
    content_type = models.ForeignKey(ContentType, models.CASCADE)
    object_id = models.PositiveIntegerField()
    rekord = GenericForeignKey()
    grant = models.ForeignKey(Grant, models.PROTECT)

    class Meta:
        verbose_name = "grant rekordu"
        verbose_name_plural = "granty rekordu"

        unique_together = [("grant", "content_type", "object_id")]

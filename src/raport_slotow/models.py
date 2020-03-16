from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models.deletion import DO_NOTHING
from django.db.models.query import QuerySet
from django_group_by import GroupByMixin

from bpp.fields import YearField
from bpp.models import (
    Rekord,
    Zrodlo,
    Charakter_Formalny,
    Autor,
    Dyscyplina_Naukowa,
    Autorzy,
    Autor_Dyscyplina,
)


class RaportZerowyQuerySet(QuerySet, GroupByMixin):
    pass


class RaportZerowyEntry(models.Model):
    objects = RaportZerowyQuerySet.as_manager()

    id = models.IntegerField(primary_key=True)
    autor = models.ForeignKey("bpp.Autor", DO_NOTHING)  # , primary_key=True)
    rok = YearField()
    dyscyplina_naukowa = models.ForeignKey("bpp.Dyscyplina_Naukowa", DO_NOTHING)

    class Meta:
        managed = False
        ordering = ("autor", "dyscyplina_naukowa")


class RaportUczelniaEwaluacjaView(models.Model):
    id = ArrayField(models.PositiveIntegerField(), 4, primary_key=True)

    rekord = models.ForeignKey(Rekord, DO_NOTHING, related_name="+")
    autorzy = models.ForeignKey(Autorzy, DO_NOTHING, related_name="+")
    autor_dyscyplina = models.ForeignKey(Autor_Dyscyplina, DO_NOTHING, related_name="+")

    autorzy_z_dyscypliny = ArrayField(models.TextField())
    pkdaut = models.DecimalField(max_digits=20, decimal_places=4)
    slot = models.DecimalField(max_digits=20, decimal_places=4)

    class Meta:
        managed = False
        ordering = ("rekord__tytul_oryginalny", "autorzy__kolejnosc")
        db_table = "bpp_uczelnia_ewaluacja_view"

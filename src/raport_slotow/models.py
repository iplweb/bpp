from django.db import models
from django.db.models.deletion import DO_NOTHING
from django.db.models.query import QuerySet
from django_group_by import GroupByMixin

from bpp.fields import YearField


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

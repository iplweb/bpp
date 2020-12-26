# -*- encoding: utf-8 -*-
from django.db import models
from django.db.models import DO_NOTHING, QuerySet
from django_group_by.mixin import GroupByMixin

from bpp.models import ModelPunktowany, ModelZLiczbaCytowan, ModelZeStatusem


# Poniżej ważne jest to on_delete=DO_NOTHING, ponieważ bez tego Django
# będzie próbowało usuwać dane z tych tabel również, a te tabele to
# są VIEWs od strony SQLa, więc to się na ten moment nie uda (nie licząc
# tych VIEWs w PostgreSQL, które są modyfikowalne...)


class Nowe_SumyQuerySet(QuerySet, GroupByMixin):
    pass


class Nowe_Sumy_View(ModelZLiczbaCytowan, ModelPunktowany, models.Model):
    autor = models.OneToOneField("Autor", on_delete=DO_NOTHING)
    jednostka = models.OneToOneField("Jednostka", on_delete=DO_NOTHING)
    wydzial = models.ForeignKey("Wydzial", on_delete=DO_NOTHING)
    rok = models.IntegerField()

    afiliuje = models.BooleanField()

    status_korekty = models.ForeignKey("Status_Korekty", DO_NOTHING)

    objects = Nowe_SumyQuerySet.as_manager()

    class Meta:
        app_label = "bpp"
        managed = False
        unique_together = ("autor", "jednostka", "wydzial", "rok")


Sumy = Nowe_Sumy_View

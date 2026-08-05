from django.db import models
from django.db.models import DO_NOTHING, QuerySet
from django_group_by.mixin import GroupByMixin

from bpp.models import ModelPunktowany, ModelZLiczbaCytowan

# Poniżej ważne jest to on_delete=DO_NOTHING, ponieważ bez tego Django
# będzie próbowało usuwać dane z tych tabel również, a te tabele to
# są VIEWs od strony SQLa, więc to się na ten moment nie uda (nie licząc
# tych VIEWs w PostgreSQL, które są modyfikowalne...)


class Nowe_SumyQuerySet(QuerySet, GroupByMixin):
    pass


class Nowe_Sumy_View(ModelZLiczbaCytowan, ModelPunktowany, models.Model):
    autor = models.OneToOneField("Autor", on_delete=DO_NOTHING)
    jednostka = models.OneToOneField("Jednostka", on_delete=DO_NOTHING)
    # Faza B (#438): kolumna widoku ``wydzial_id`` to teraz
    # ``bpp_jednostka.wydzial_id`` = jednostka-korzeń (self-FK), nie Wydzial.
    # ``related_name="+"`` — oba pola (``jednostka`` i ``wydzial``) celują w
    # Jednostkę, więc bez tego kolidują odwrotne akcesory (fields.E305).
    # ``null=True`` (F7): kolumna widoku jest nullable dla jednostek-korzeni
    # (``wydzial=NULL``); bez tego ``__str__`` (``{self.wydzial=}``) rzuca
    # ``RelatedObjectDoesNotExist`` na wierszu korzenia. Model na widoku
    # (``managed=False``) — zmiana wyłącznie stanu, nie dotyka DDL.
    wydzial = models.ForeignKey(
        "Jednostka", on_delete=DO_NOTHING, related_name="+", null=True
    )
    rok = models.IntegerField()

    afiliuje = models.BooleanField()

    status_korekty = models.ForeignKey("Status_Korekty", DO_NOTHING)

    # New fields for filtering
    charakter_formalny = models.ForeignKey(
        "Charakter_Formalny", DO_NOTHING, null=True, blank=True
    )
    typ_kbn = models.ForeignKey("Typ_KBN", DO_NOTHING, null=True, blank=True)

    objects = Nowe_SumyQuerySet.as_manager()

    class Meta:
        app_label = "bpp"
        managed = False
        unique_together = ("autor", "jednostka", "wydzial", "rok")

    def __str__(self):
        return (
            f"{self.autor=} {self.jednostka=} {self.wydzial=} "
            f"{self.rok=} {self.impact_factor=} {self.punkty_kbn=}"
        )


Sumy = Nowe_Sumy_View

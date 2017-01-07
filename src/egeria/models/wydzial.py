# -*- encoding: utf-8 -*-
from datetime import timedelta
from django.db import models

from bpp.models import Wydzial
from egeria.models.abstract import Diff_Delete, Diff_Create
from .util import zrob_skrot


class Diff_Wydzial_Create(Diff_Create):
    klass = Wydzial

    def commit(self):
        self.klass.objects.create(
            nazwa=self.nazwa_skrot,
            skrot=zrob_skrot(self.nazwa_skrot, max_length=4, klasa=Wydzial, atrybut='skrot'),
            uczelnia=self.parent.uczelnia,
            otwarcie=self.parent.od,
            zamkniecie=self.parent.do)
        super(Diff_Create, self).commit()


class Diff_Wydzial_Delete(Diff_Delete):
    reference = models.ForeignKey(Wydzial)

    @classmethod
    def check_if_needed(cls, parent, reference):
        if reference.jednostka_set.count() == 0:
            return True

        if reference.widoczny == False and reference.zezwalaj_na_ranking_autorow == False:
            return False

        return True

    def has_linked_units(self):
        return self.reference.jednostka_set.count() > 0

    def commit(self):
        # Jeżeli ma jakiekolwiek jednostki w sobie, to zaznacz jako niewidoczny.
        if not self.has_linked_units():
            super(Diff_Wydzial_Delete, self).commit()
        else:
            self.reference.widoczny = False
            self.reference.zezwalaj_na_ranking_autorow = False
            self.reference.zamkniecie = self.parent.od - timedelta(days=1)
            self.reference.save()
            self.delete()

# -*- encoding: utf-8 -*-
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from django.db import models
from django.conf import settings

# Create your models here.
from bpp.models.struktura import Wydzial


class PlikEksportuPBN(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL)
    created_on = models.DateTimeField(auto_now_add=True)
    file = models.FileField(verbose_name="Plik", upload_to="eksport_pbn")

    wydzial = models.ForeignKey(Wydzial)
    rok = models.IntegerField(choices=[(2013, '2013'),
                                       (2014, '2014'),
                                       (2015, '2015')],
                              default=2015)

    artykuly = models.BooleanField("Artykuły", default=True)
    ksiazki = models.BooleanField("Książki", default=True)
    rozdzialy = models.BooleanField("Rozdziały", default=True)

    # PLAN
    #
    # 1) eksportowanie POJEDYNCZYCH prac
    # 2) parametryzacja pola "redaktor", "strony", etc
    # 3) parser do pola "uwagi" ORAZ globalne sprawdzenie tabel pod katem tego, czy da sie je tak podzielic
    # 4) skrypt w SELENIUM czy w innym browser poserze wrzucajacy eksport na strone?

    def get_fn(self):
        buf = u"PBN-%s-%s" % (self.wydzial.skrot, self.rok)

        if self.artykuly and self.ksiazki and self.rozdzialy:
            return buf

        extra = [
            (self.artykuly, u"art"),
            (self.ksiazki, u"ksi"),
            (self.rozdzialy, u"roz")
        ]

        for b, val in extra:
            if b:
                buf += u"-" + val

        return buf
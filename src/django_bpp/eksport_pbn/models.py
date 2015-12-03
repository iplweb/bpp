# -*- encoding: utf-8 -*-
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models
# Create your models here.
from bpp.models.struktura import Wydzial

DATE_CREATED_ON, DATE_UPDATED_ON = (1, 2)


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

    od_daty = models.DateField(verbose_name="Od daty", blank=True, null=True)

    do_daty = models.DateField(verbose_name="Od daty", blank=True, null=True)

    rodzaj_daty = models.SmallIntegerField(
        verbose_name="Rodzaj pola daty",
        choices=[(DATE_CREATED_ON, "data utworzenia"),
                 (DATE_UPDATED_ON, "data aktualizacji")],
        default=0,
        help_text="""Jakie pole z datą będzie używane do wybierania rekordów?""")

    # PLAN
    #
    # 1) eksportowanie POJEDYNCZYCH prac
    # 2) parametryzacja pola "redaktor", "strony", etc
    # 3) parser do pola "uwagi" ORAZ globalne sprawdzenie tabel pod katem tego, czy da sie je tak podzielic
    # 4) skrypt w SELENIUM czy w innym browser poserze wrzucajacy eksport na strone?

    def get_fn(self):
        buf = u"PBN-%s-%s" % (self.wydzial.skrot, self.rok)

        if not (self.artykuly and self.ksiazki and self.rozdzialy):

            extra = [
                (self.artykuly, u"art"),
                (self.ksiazki, u"ksi"),
                (self.rozdzialy, u"roz")
            ]

            for b, val in extra:
                if b:
                    buf += u"-" + val

        flds = { DATE_CREATED_ON: 'utw',
                 DATE_UPDATED_ON: 'zm' }

        if self.od_daty:
            try:
                buf += "-" + flds[self.rodzaj_daty]
            except KeyError:
                from tasks import BrakTakiegoRodzajuDatyException
                raise BrakTakiegoRodzajuDatyException(self.rodzaj_daty)

            for label, wartosc in [('od', self.od_daty), ('do', self.do_daty)]:
                if wartosc is None:
                    continue
                buf += "-" + label + "-"
                buf += str(wartosc).replace("-", "_").replace("/", "_")
        return buf

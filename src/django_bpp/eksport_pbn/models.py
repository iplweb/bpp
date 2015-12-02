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

    data = models.DateField(
        verbose_name="Data",
        help_text="""Data aktualizacji lub utworzenia rekordu większa od lub równa. Jeżeli pozostawisz
        to pole puste, data nie będzie używana przy generowaniu pliku. """,
        blank=True, null=True)

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

        if self.data:

            if self.rodzaj_daty == DATE_CREATED_ON:
                buf += "-utw_po-"
            elif self.rodzaj_daty == DATE_UPDATED_ON:
                buf += "-zm_po-"
            else:
                from tasks import BrakTakiegoRodzajuDatyException
                raise BrakTakiegoRodzajuDatyException(self.rodzaj_daty)

            buf += str(self.data).replace("-", "_").replace("/", "_")
        return buf

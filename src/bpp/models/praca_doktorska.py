# -*- encoding: utf-8 -*-

from django.db import models

from .autor import Autor
from .struktura import Jednostka
from .system import Typ_Odpowiedzialnosci
from .wydawnictwo_zwarte import Wydawnictwo_Zwarte_Baza


class Praca_Doktorska_Baza(Wydawnictwo_Zwarte_Baza):

    autor = models.OneToOneField(Autor)
    jednostka = models.ForeignKey(Jednostka)

    @property
    def autorzy_set(self):
        class FakeAutorDoktoratuHabilitacji:
            autor = self.autor
            jednostka = self.jednostka
            zapisany_jako = f"{ autor.nazwisko or '' } { autor.imiona or '' }"

        class FakeSet:
            def all(self):
                ret = FakeAutorDoktoratuHabilitacji()
                ret.typ_odpowiedzialnosci = Typ_Odpowiedzialnosci.objects.get(
                    skrot="aut.")
                return [ret]

        return FakeSet()

    class Meta:
        abstract = True


class Praca_Doktorska(Praca_Doktorska_Baza):

    promotor = models.ForeignKey(Autor, related_name="promotor_doktoratu", blank=True, null=True)

    class Meta:
        verbose_name = 'praca doktorska'
        verbose_name_plural = 'prace doktorskie'
        app_label = 'bpp'

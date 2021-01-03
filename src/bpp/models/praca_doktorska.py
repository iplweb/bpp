# -*- encoding: utf-8 -*-

from django.db import models
from django.db.models import CASCADE, SET_NULL
from .autor import Autor
from .struktura import Jednostka
from .system import Typ_Odpowiedzialnosci
from .wydawnictwo_zwarte import Wydawnictwo_Zwarte_Baza

from django.utils.functional import cached_property

from bpp.models import Charakter_Formalny, NieMaProcentowMixin


class Praca_Doktorska_Baza(NieMaProcentowMixin, Wydawnictwo_Zwarte_Baza):

    jednostka = models.ForeignKey(Jednostka, CASCADE)

    @property
    def autorzy_set(self):
        class FakeAutorDoktoratuHabilitacji:
            autor = self.autor
            jednostka = self.jednostka
            zapisany_jako = f"{ autor.nazwisko or '' } { autor.imiona or '' }"

        class FakeSet(list):
            def all(self):
                return self

        ret = FakeAutorDoktoratuHabilitacji()
        ret.typ_odpowiedzialnosci = Typ_Odpowiedzialnosci.objects.get(skrot="aut.")
        return FakeSet([ret])

    def autorzy_dla_opisu(self):
        return self.autorzy_set

    class Meta:
        abstract = True


class Praca_Doktorska(Praca_Doktorska_Baza):
    autor = models.ForeignKey(Autor, CASCADE)

    promotor = models.ForeignKey(
        Autor, SET_NULL, related_name="promotor_doktoratu", blank=True, null=True
    )

    @cached_property
    def charakter_formalny(self):
        return Charakter_Formalny.objects.get(skrot="D")

    class Meta:
        verbose_name = "praca doktorska"
        verbose_name_plural = "prace doktorskie"
        app_label = "bpp"
        ordering = ("rok", "tytul_oryginalny")

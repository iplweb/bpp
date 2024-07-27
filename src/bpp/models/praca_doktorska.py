from denorm import denormalized, depend_on_related
from django.db import models
from django.db.models import CASCADE, SET_NULL

from .autor import Autor
from .struktura import Jednostka
from .system import Typ_Odpowiedzialnosci
from .wydawnictwo_zwarte import Wydawnictwo_Zwarte_Baza

from django.contrib.postgres.fields import ArrayField

from django.utils.functional import cached_property

from bpp.models import (
    Charakter_Formalny,
    ModelZOplataZaPublikacje,
    ModelZPBN_UID,
    NieMaProcentowMixin,
)
from bpp.models.abstract import DwaTytuly


class Praca_Doktorska_Baza(
    NieMaProcentowMixin,
    ModelZPBN_UID,
    ModelZOplataZaPublikacje,
    Wydawnictwo_Zwarte_Baza,
):

    jednostka = models.ForeignKey(Jednostka, CASCADE)

    @property
    def autorzy_set(self):
        class FakeAutorDoktoratuHabilitacji:
            autor = self.autor
            jednostka = self.jednostka
            zapisany_jako = f"{autor.nazwisko or ''} {autor.imiona or ''}"

        class FakeSet(list):
            def all(self):
                return self

            def select_related(self, *args, **kw):
                return self

            def odpiete_dyscypliny(self, *args, **kw):
                return FakeSet([])

            def exclude(self, *args, **kw):
                return self

            def exists(self):
                return False

        ret = FakeAutorDoktoratuHabilitacji()
        ret.typ_odpowiedzialnosci = Typ_Odpowiedzialnosci.objects.get(skrot="aut.")
        return FakeSet([ret])

    def autorzy_dla_opisu(self):
        return self.autorzy_set

    class Meta:
        abstract = True

    #
    # Cache framework by django-denorm-iplweb
    #

    denorm_always_skip = ("ostatnio_zmieniony",)

    @denormalized(models.TextField, default="")
    @depend_on_related(
        "bpp.Autor",
        foreign_key="autor",
        only=("nazwisko", "imiona", "tytul_id"),
    )
    @depend_on_related("bpp.Jednostka", only=("nazwa", "skrot", "wydzial_id"))
    @depend_on_related("bpp.Status_Korekty")
    def opis_bibliograficzny_cache(self):
        return self.opis_bibliograficzny()

    @denormalized(ArrayField, base_field=models.TextField(), blank=True, null=True)
    @depend_on_related(
        "bpp.Autor",
        foreign_key="autor",
        only=(
            "nazwisko",
            "imiona",
        ),
    )
    def opis_bibliograficzny_autorzy_cache(self):
        return [f"{self.autor.nazwisko} {self.autor.imiona}"]

    @denormalized(models.TextField, blank=True, null=True)
    @depend_on_related(
        "bpp.Autor",
        foreign_key="autor",
        only=(
            "nazwisko",
            "imiona",
        ),
    )
    def opis_bibliograficzny_zapisani_autorzy_cache(self):
        return f"{self.autor.nazwisko} {self.autor.imiona}"

    @denormalized(
        models.SlugField,
        max_length=400,
        unique=True,
        db_index=True,
        null=True,
        blank=True,
    )
    @depend_on_related(
        "bpp.Autor",
        foreign_key="autor",
        only=("nazwisko", "imiona"),
    )
    def slug(self):
        return self.get_slug()


class _Praca_Doktorska_PropertyCache:
    @cached_property
    def charakter_formalny(self):
        return Charakter_Formalny.objects.get(skrot="D")


_Praca_Doktorska_PropertyCache = _Praca_Doktorska_PropertyCache()


class Praca_Doktorska(Praca_Doktorska_Baza):
    autor = models.ForeignKey(Autor, CASCADE)

    promotor = models.ForeignKey(
        Autor, SET_NULL, related_name="promotor_doktoratu", blank=True, null=True
    )

    @cached_property
    def charakter_formalny(self):
        return _Praca_Doktorska_PropertyCache.charakter_formalny

    class Meta:
        verbose_name = "praca doktorska"
        verbose_name_plural = "prace doktorskie"
        app_label = "bpp"
        ordering = ("rok", "tytul_oryginalny")

    def clean(self):
        DwaTytuly.clean(self)
        ModelZOplataZaPublikacje.clean(self)

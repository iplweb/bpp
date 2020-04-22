# -*- encoding: utf-8 -*-

"""
Struktura uczelni.
"""

from autoslug import AutoSlugField
from django.db import models
from django.db.models import CASCADE
from django.urls.base import reverse

from bpp.models import ModelZAdnotacjami
from bpp.models.abstract import ModelZPBN_ID
from bpp.util import FulltextSearchMixin
from .uczelnia import Uczelnia


class Wydzial(ModelZAdnotacjami, ModelZPBN_ID):
    uczelnia = models.ForeignKey(Uczelnia, CASCADE)
    nazwa = models.CharField(
        max_length=512,
        unique=True,
        help_text='Pełna nazwa wydziału, np. "Wydział Lekarski"',
    )
    skrot_nazwy = models.CharField(
        max_length=250,
        unique=True,
        blank=True,
        null=True,
        help_text='Skrót nazwy wydziału, wersja czytelna, np. "Wydz. Lek."',
    )
    skrot = models.CharField(
        "Skrót",
        max_length=10,
        unique=True,
        help_text='Skrót nazwy wydziału, wersja minimalna, np. "WL"',
    )

    opis = models.TextField(null=True, blank=True)
    slug = AutoSlugField(populate_from="nazwa", max_length=512, unique=True)
    poprzednie_nazwy = models.CharField(
        max_length=4096, blank=True, null=True, default=""
    )
    kolejnosc = models.IntegerField("Kolejność", default=0)
    widoczny = models.BooleanField(
        default=True,
        help_text="""Czy wydział ma być widoczny przy przeglądaniu strony dla zakładki "Uczelnia"?""",
    )

    zezwalaj_na_ranking_autorow = models.BooleanField(
        "Zezwalaj na generowanie rankingu autorów dla tego wydziału", default=True
    )

    zarzadzaj_automatycznie = models.BooleanField(
        "Zarządzaj automatycznie",
        default=True,
        help_text="""Wydział ten będzie dowolnie modyfikowany przez procedury importujace dane z zewnętrznych
        systemów informatycznych. W przypadku, gdy pole ma ustawioną wartość na 'fałsz', wydział ten może być""",
    )

    otwarcie = models.DateField("Data otwarcia wydziału", blank=True, null=True)
    zamkniecie = models.DateField("Data zamknięcia wydziału", blank=True, null=True)

    class Meta:
        verbose_name = "wydział"
        verbose_name_plural = "wydziały"
        ordering = ["kolejnosc", "skrot"]
        app_label = "bpp"

    def __str__(self):
        return self.nazwa

    def get_absolute_url(self):
        return reverse("bpp:browse_wydzial", args=(self.slug,))

    def jednostki(self):
        """Lista jednostek - dla WWW"""
        from .jednostka import Jednostka

        return Jednostka.objects.filter(wydzial=self, widoczna=True).order_by(
            *Jednostka.objects.get_default_ordering()
        )


class JednostkaManager(FulltextSearchMixin, models.Manager):
    def create(self, *args, **kw):
        if "wydzial" in kw and not ("uczelnia" in kw or "uczelnia_id" in kw):
            # Kompatybilność wsteczna, z czasów, gdy nie było metryczki historycznej
            # dla obecności jednostki w wydziałach
            kw["uczelnia"] = kw["wydzial"].uczelnia
        return super(JednostkaManager, self).create(*args, **kw)

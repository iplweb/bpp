"""
Modele abstrakcyjne związane z nazwami.
"""

from django.db import models

from bpp.util import safe_html


class ModelZNazwa(models.Model):
    """Nazwany model."""

    nazwa = models.CharField(max_length=512, unique=True)

    class Meta:
        abstract = True
        ordering = ["nazwa"]

    def __str__(self):
        return self.nazwa


class NazwaISkrot(ModelZNazwa):
    """Model z nazwą i ze skrótem"""

    skrot = models.CharField(max_length=128, unique=True)

    class Meta:
        abstract = True


class NazwaWDopelniaczu(models.Model):
    nazwa_dopelniacz_field = models.CharField(
        "Nazwa w dopełniaczu", max_length=512, blank=True, default=""
    )

    class Meta:
        abstract = True

    def nazwa_dopelniacz(self):
        if not hasattr(self, "nazwa"):
            return self.nazwa_dopelniacz_field
        if self.nazwa_dopelniacz_field is None or self.nazwa_dopelniacz_field == "":
            return self.nazwa
        return self.nazwa_dopelniacz_field


class DwaTytuly(models.Model):
    """Model zawierający dwa tytuły: tytuł oryginalny pracy oraz tytuł
    przetłumaczony."""

    tytul_oryginalny = models.TextField("Tytuł oryginalny", db_index=True)
    tytul = models.TextField("Tytuł", blank=True, default="", db_index=True)

    class Meta:
        abstract = True

    def clean(self):
        self.tytul_oryginalny = safe_html(self.tytul_oryginalny)
        self.tytul = safe_html(self.tytul)

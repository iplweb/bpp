from django.db import models

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

# Create your models here.
from bpp.models.abstract import (
    BazaModeluOdpowiedzialnosciAutorow,
    DwaTytuly,
    ModelZDOI,
    ModelZOplataZaPublikacje,
    ModelZWWW,
    nie_zawiera_adresu_doi_org,
    nie_zawiera_http_https,
)


class Zgloszenie_Publikacji(
    ModelZWWW,
    DwaTytuly,
    ModelZDOI,
    ModelZOplataZaPublikacje,
):
    email = models.EmailField("E-mail zgłaszającego")

    utworzono = models.DateTimeField(
        "Utworzono", auto_now_add=True, blank=True, null=True
    )

    object_id = models.BigIntegerField(null=True, blank=True)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True
    )
    odpowiednik_w_bpp = GenericForeignKey()

    status = models.PositiveSmallIntegerField(
        default=0,
        choices=[
            (0, "nowe zgłoszenie"),
            (1, "dodane do bazy"),
            (2, "wymaga uzupełnienia"),
            (3, "odrzucono"),
            (4, "spam"),
        ],
    )

    def clean(self):
        ModelZOplataZaPublikacje.clean(self)
        if self.doi:
            nie_zawiera_http_https(self.doi)
        if self.www:
            nie_zawiera_adresu_doi_org(self.www)
        if self.public_www:
            nie_zawiera_adresu_doi_org(self.public_www)

    def __str__(self):
        return f"Zgłoszenie od {self.email} utworzone {self.utworzono} dla pracy {self.tytul_oryginalny}"

    class Meta:
        verbose_name = "zgłoszenie publikacji"
        verbose_name_plural = "zgłoszenia publikacji"
        ordering = ("-utworzono", "tytul_oryginalny")


class Zgloszenie_Publikacji_Autor(BazaModeluOdpowiedzialnosciAutorow):
    rekord = models.ForeignKey(Zgloszenie_Publikacji, on_delete=models.CASCADE)

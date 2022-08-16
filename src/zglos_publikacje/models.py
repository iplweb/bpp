import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from bpp.models import Autor_Dyscyplina
from bpp.models.abstract import (
    BazaModeluOdpowiedzialnosciAutorow,
    DwaTytuly,
    ModelZDOI,
    ModelZOplataZaPublikacje,
    ModelZRokiem,
)


class Zgloszenie_Publikacji(
    ModelZRokiem,
    DwaTytuly,
    ModelZDOI,
    ModelZOplataZaPublikacje,
):
    email = models.EmailField("E-mail zgłaszającego")

    utworzono = models.DateTimeField(
        "Utworzono", auto_now_add=True, blank=True, null=True
    )

    ostatnio_zmieniony = models.DateTimeField(auto_now=True, null=True, db_index=True)

    object_id = models.BigIntegerField(null=True, blank=True)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True
    )
    odpowiednik_w_bpp = GenericForeignKey()

    kod_do_edycji = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, null=True, blank=True
    )
    przyczyna_zwrotu = models.TextField(blank=True, null=True)

    class Statusy(models.IntegerChoices):
        NOWY = 0, "nowe zgłoszenie"
        ZAAKCEPTOWANY = 1, "zaakceptowany - dodany do bazy BPP"
        WYMAGA_ZMIAN = 2, "wymaga zmian - odesłano do zgłaszającego"
        PO_ZMIANACH = 3, "zmiany naniesione przez zgłaszającego"
        ODRZUCONO = 4, "odrzucono w całości"
        SPAM = 5, "spam"

    status = models.PositiveSmallIntegerField(
        default=Statusy.NOWY, choices=Statusy.choices
    )

    strona_www = models.URLField(
        "Dostępna w sieci pod adresem",
        help_text="Pole opcjonalne. Adres URL lokalizacji pełnego tekstu pracy (dostęp otwarty lub nie). "
        "Jeżeli praca posiada numer DOI, wpisz go w postaci adresu URL czyli https://dx.doi.org/[NUMER_DOI]. "
        "Jeżeli praca nie posiada numeru DOI bądź nie jest dostępna w sieci, pozostaw to pole puste. ",
        max_length=1024,
        blank=True,
        null=True,
    )

    plik = models.FileField(
        "Plik załącznika",
        help_text="""Jeżeli zgłaszana publikacja nie jest dostępna nigdzie w sieci internet,
        prosimy o dodanie załącznika""",
        blank=True,
        null=True,
    )

    def clean(self):
        ModelZOplataZaPublikacje.clean(self)

    def __str__(self):
        return f"Zgłoszenie od {self.email} utworzone {self.utworzono} dla pracy {self.tytul_oryginalny}"

    class Meta:
        verbose_name = "zgłoszenie publikacji"
        verbose_name_plural = "zgłoszenia publikacji"
        ordering = ("-ostatnio_zmieniony", "tytul_oryginalny")

    def moze_zostac_zwrocony(self):
        return self.status in [
            Zgloszenie_Publikacji.Statusy.NOWY,
            Zgloszenie_Publikacji.Statusy.PO_ZMIANACH,
        ]


class Zgloszenie_Publikacji_Autor(BazaModeluOdpowiedzialnosciAutorow):
    rekord = models.ForeignKey(Zgloszenie_Publikacji, on_delete=models.CASCADE)

    rok = models.PositiveSmallIntegerField()

    class Meta:
        verbose_name = "autor w zgłoszeniu publikacji"
        verbose_name_plural = "autorzy w zgłoszeniu publikacji"
        ordering = ("kolejnosc",)

    def __str__(self):
        return f"autor {self.autor} dla zgłoszenia publikacji {self.rekord.tytul_oryginalny}"

    def clean(self):

        if self.autor_id is None:
            raise ValidationError({"autor": "Wybierz jakiegoś autora"})

        przypisanie_na_rok_istnieje = Autor_Dyscyplina.objects.filter(
            autor=self.autor,
            rok=self.rok,
        ).exists()

        if przypisanie_na_rok_istnieje and self.dyscyplina_naukowa_id is None:
            raise ValidationError(
                {
                    "dyscyplina_naukowa": f"Autor {self.autor} ma przypisaną przynajmniej jedną dyscyplinę na rok "
                    f"{self.rok} i z tego powodu to pole nie może być puste. "
                }
            )

        if self.dyscyplina_naukowa is not None:
            try:
                Autor_Dyscyplina.objects.get(
                    Q(dyscyplina_naukowa=self.dyscyplina_naukowa)
                    | Q(subdyscyplina_naukowa=self.dyscyplina_naukowa),
                    autor=self.autor,
                    rok=self.rok,
                )
            except Autor_Dyscyplina.DoesNotExist:
                raise ValidationError(
                    {
                        "dyscyplina_naukowa": f"Autor {self.autor} nie ma przypisania na "
                        f"rok {self.rok} do dyscypliny {self.dyscyplina_naukowa}."
                    }
                )

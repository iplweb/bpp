from collections import defaultdict

from django.db import models

from bpp.models.abstract import ModelZAdnotacjami, ModelZNazwa


class Konferencja(ModelZNazwa, ModelZAdnotacjami):
    nazwa = models.CharField(max_length=512, db_index=True)

    skrocona_nazwa = models.CharField(
        "Skrócona nazwa", max_length=250, null=True, blank=True, db_index=True
    )

    rozpoczecie = models.DateField("Rozpoczęcie", null=True, blank=True)

    zakonczenie = models.DateField("Zakończenie", null=True, blank=True)

    miasto = models.CharField("Miasto", max_length=100, null=True, blank=True)

    panstwo = models.CharField("Państwo", max_length=100, null=True, blank=True)

    baza_scopus = models.BooleanField("Indeksowana w SCOPUS?", default=False)

    baza_wos = models.BooleanField("Indeksowana w WOS?", default=False)

    baza_inna = models.CharField(
        "Indeksowana w...",
        max_length=200,
        help_text="Wpisz listę innych baz czasopism i abstraktów, w których indeksowana "
        "była ta konferencja. Rozdziel średnikiem.",
        blank=True,
        null=True,
    )

    pbn_uid = models.ForeignKey(
        "pbn_api.Conference",
        verbose_name="Odpowiednik w PBN",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    TK_KRAJOWA = 1
    TK_MIEDZYNARODOWA = 2
    TK_LOKALNA = 3

    TK_KRAJOWA_SYMBOL = "🚆 "
    TK_MIEDZYNARODOWA_SYMBOL = "✈ "
    TK_LOKALNA_SYMBOL = "🚲 "

    TK_SYMBOLE = defaultdict(
        lambda: "",
        {
            TK_KRAJOWA: TK_KRAJOWA_SYMBOL,
            TK_MIEDZYNARODOWA: TK_MIEDZYNARODOWA_SYMBOL,
            TK_LOKALNA: TK_LOKALNA_SYMBOL,
        },
    )

    TYP_KONFERENCJI_CHOICES = (
        (TK_KRAJOWA, TK_SYMBOLE[TK_KRAJOWA] + "krajowa"),
        (TK_MIEDZYNARODOWA, TK_SYMBOLE[TK_MIEDZYNARODOWA] + "️międzynarodowa"),
        (TK_LOKALNA, TK_SYMBOLE[TK_LOKALNA] + "lokalna"),
    )

    typ_konferencji = models.SmallIntegerField(
        choices=TYP_KONFERENCJI_CHOICES, null=True, blank=True
    )

    class Meta:
        unique_together = ("nazwa", "rozpoczecie")
        ordering = ("-rozpoczecie", "nazwa")
        verbose_name = "konferencja"
        verbose_name_plural = "konferencje"

    def __str__(self):
        ret = self.nazwa
        if self.baza_scopus:
            ret += " [Scopus]"
        if self.baza_wos:
            ret += " [WoS]"
        if self.baza_inna:
            ret += f" [{self.baza_inna}]"
        return ret

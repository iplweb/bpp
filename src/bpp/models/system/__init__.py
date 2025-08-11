"""
Małe klasy pomocnicze dla całego systemu
"""

from django.db import models
from django.db.models import CASCADE

from .charakter_formalny import *  # noqa
from .crossref_mapper import *  # noqa

from bpp import const
from bpp.models.abstract import ModelZNazwa, NazwaISkrot


class Status_Korekty(ModelZNazwa):
    class Meta:
        verbose_name = "status korekty"
        verbose_name_plural = "statusy korekty"
        app_label = "bpp"


class Zrodlo_Informacji(ModelZNazwa):
    class Meta:
        verbose_name = "źródło informacji o bibliografii"
        verbose_name_plural = "źródła informacji o bibliografii"
        app_label = "bpp"


class Typ_Odpowiedzialnosci(NazwaISkrot):
    typ_ogolny = models.SmallIntegerField(
        "Ogólny typ odpowiedzialności",
        choices=[
            (const.TO_AUTOR, "autor"),
            (const.TO_REDAKTOR, "redaktor"),
            (const.TO_INNY, "inny"),
            (const.TO_TLUMACZ, "tłumacz"),
            (const.TO_KOMENTATOR, "komentator"),
            (const.TO_RECENZENT, "recenzent"),
            (const.TO_OPRACOWAL, "opracował"),
            (const.TO_REDAKTOR_TLUMACZENIA, "redaktor tłumaczenia"),
        ],
        default=const.TO_AUTOR,
        help_text="""Pole to jest używane celem rozróżniania typu odpowiedzialności
        na cele eksportu do PBN (autor i redaktor) oraz może być też wykorzystywane
        np. w raportach autorów i jednostek.
        """,
        db_index=True,
    )

    class Meta:
        verbose_name = "typ odpowiedzialności"
        verbose_name_plural = "typy odpowiedzialności"
        ordering = ["nazwa"]
        app_label = "bpp"

    def __str__(self):
        return self.nazwa


class Jezyk(NazwaISkrot):
    class SKROT_CROSSREF(models.TextChoices):
        en = "en", "en - angielski"
        es = "es", "es - hiszpański"

    skrot_crossref = models.CharField(
        max_length=10,
        verbose_name="Skrót nazwy języka wg API CrossRef",
        choices=SKROT_CROSSREF.choices,
        blank=True,
        null=True,
        unique=True,
    )

    pbn_uid = models.ForeignKey(
        "pbn_api.Language", null=True, blank=True, on_delete=models.SET_NULL
    )

    widoczny = models.BooleanField(default=True)

    class Meta:
        verbose_name = "język"
        verbose_name_plural = "języki"
        ordering = ["nazwa"]
        app_label = "bpp"

    def get_skrot_dla_pbn(self):
        if self.skrot_dla_pbn:
            return self.skrot_dla_pbn

        return self.skrot


class Typ_KBN(NazwaISkrot):
    artykul_pbn = models.BooleanField(
        "Artykuł w PBN",
        help_text="""Wydawnictwa ciągłe posiadające
    ten typ MNiSW/MEiN zostaną włączone do eksportu PBN jako artykuły""",
        default=False,
    )

    charakter_pbn = models.ForeignKey(
        "bpp.Charakter_PBN",
        verbose_name="Charakter PBN",
        blank=True,
        null=True,
        default=None,
        help_text="""Wartość wybrana w tym polu zostanie użyta jako
        fallback, tzn. jeżeli dla charakteru formalnego danego rekordu nie
        określono odpowiedniego charakteru PBN, to zostanie użyta wartość
        tego pola, o ile wybrana. """,
        on_delete=CASCADE,
    )

    wliczaj_do_rankingu = models.BooleanField(default=True)

    class Meta:
        verbose_name = "typ MNiSW/MEiN"
        verbose_name_plural = "typy KBN"
        ordering = ["nazwa"]
        app_label = "bpp"


class Rodzaj_Prawa_Patentowego(ModelZNazwa):
    class Meta:
        verbose_name = "rodzaj prawa patentowego"
        verbose_name_plural = "rodzaje praw patentowych"
        ordering = [
            "nazwa",
        ]
        app_label = "bpp"


class Zewnetrzna_Baza_Danych(NazwaISkrot):
    class Meta:
        verbose_name = "zewnętrzna baza danych"
        verbose_name_plural = "zenwętrzne bazy danych"
        ordering = [
            "nazwa",
        ]
        app_label = "bpp"

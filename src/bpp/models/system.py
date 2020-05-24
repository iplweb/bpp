# -*- encoding: utf-8 -*-

"""
Małe klasy pomocnicze dla całego systemu
"""
import warnings

from django.db import models
from django.db.models import CASCADE
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from model_utils import Choices
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel

from bpp.models import const
from bpp.models.abstract import ModelZNazwa, NazwaISkrot

NAZWY_PRIMO = [
    "",
    "Artykuł",
    "Książka",
    "Zasób tekstowy",
    "Rozprawa naukowa",
    "Recenzja",
    "Artykuł prasowy",
    "Rozdział",
    "Czasopismo",
    "Dane badawcze",
    "Materiał konferencyjny",
    "Obraz",
    "Baza",
    "Zestaw danych statystycznych",
    "Multimedia",
    "Inny",
]

NAZWY_PRIMO = list(zip(NAZWY_PRIMO, NAZWY_PRIMO))

RODZAJE_DOKUMENTOW_PBN = [
    ("article", "Artykuł"),
    ("book", "Książka"),
    ("chapter", "Rozdział"),
]


class Charakter_PBN(models.Model):
    wlasciwy_dla = models.CharField(
        "Właściwy dla...", max_length=20, choices=RODZAJE_DOKUMENTOW_PBN
    )
    identyfikator = models.CharField(max_length=100)
    opis = models.CharField(max_length=500)
    help_text = models.TextField(blank=True)

    class Meta:
        ordering = ["identyfikator"]
        verbose_name = "Charakter PBN"
        verbose_name_plural = "Charaktery PBN"

    def __str__(self):
        return self.opis


CHARAKTER_SLOTY = Choices(
    (const.CHARAKTER_SLOTY_KSIAZKA, "ksiazka", "Książka"),
    (const.CHARAKTER_SLOTY_ROZDZIAL, "rozdzial", "Rozdział"),
)

RODZAJ_PBN_CHOICES = [
    (None, "nie eksportuj do PBN"),
    (const.RODZAJ_PBN_ARTYKUL, "artykuł"),
    (const.RODZAJ_PBN_KSIAZKA, "książka"),
    (const.RODZAJ_PBN_ROZDZIAL, "rozdział"),
]

CHARAKTER_OGOLNY_CHOICES = Choices(
    (const.CHARAKTER_OGOLNY_ARTYKUL, "artykul", "Artykuł"),
    (const.CHARAKTER_OGOLNY_KSIAZKA, "ksiazka", "Książka"),
    (const.CHARAKTER_OGOLNY_ROZDZIAL, "rozdzial", "Rozdział"),
    (const.CHARAKTER_OGOLNY_INNE, "inne", "Inne"),
)


class Charakter_Formalny(NazwaISkrot, MPTTModel):
    parent = TreeForeignKey(
        "self",
        verbose_name="Charakter nadrzędny",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )

    charakter_ogolny = models.CharField(
        max_length=3,
        help_text="""Charakter ogólny uzywany jest m.in. do generowania opisów bibliograficznych. Stanowi on
        ogólne określenie rekordu, czy jest to książka, rozdział czy coś innego. """,
        default=const.CHARAKTER_OGOLNY_INNE,
        choices=CHARAKTER_OGOLNY_CHOICES,
    )

    publikacja = models.BooleanField(
        help_text="""Jest charakterem dla publikacji""", default=False
    )
    streszczenie = models.BooleanField(
        help_text="""Jest charakterem dla streszczeń""", default=False
    )

    nazwa_w_primo = models.CharField(
        "Nazwa w Primo",
        max_length=100,
        help_text="""
    Nazwa charakteru formalnego w wyszukiwarce Primo, eksponowana przez OAI-PMH. W przypadku,
    gdy to pole jest puste, prace o danym charakterze formalnym nie będą udostępniane przez
    protokół OAI-PMH.
    """,
        blank=True,
        default="",
        choices=NAZWY_PRIMO,
        db_index=True,
    )

    charakter_pbn = models.ForeignKey(
        Charakter_PBN,
        verbose_name="Charakter PBN",
        blank=True,
        null=True,
        default=None,
        help_text="""Wartość wybrana w tym polu zostanie użyta jako zawartość tagu &lt;is>
                                      w plikach eksportu do PBN""",
        on_delete=CASCADE,
    )

    rodzaj_pbn = models.PositiveSmallIntegerField(
        verbose_name="Rodzaj dla PBN",
        choices=RODZAJ_PBN_CHOICES,
        null=True,
        blank=True,
        help_text="""Pole określające, czy wydawnictwa posiadające dany charakter formalny zostaną włączone
        do eksportu PBN jako artykuły, rozdziały czy książki. """,
        default=None,
    )

    charakter_sloty = models.PositiveSmallIntegerField(
        "Charakter dla slotów",
        null=True,
        blank=True,
        default=None,
        choices=CHARAKTER_SLOTY,
        help_text="""Jak potraktować ten charakter przy kalkulacji slotów dla wydawnictwa zwartego?""",
    )

    class Meta:
        ordering = ["nazwa"]
        app_label = "bpp"
        verbose_name = "charakter formalny"
        verbose_name_plural = "charaktery formalne"

    class MPTTMeta:
        order_insertion_by = ["nazwa"]

    #
    # Kompatybilne API dla .artykul_pbn, .rozdzial_pbn, .ksiazka_pbn
    #

    def get_rodzaj(self, typ):
        warnings.warn("W przyszlosci uzyj pola 'rodzaj_pbn'", DeprecationWarning)
        v = getattr(const, "RODZAJ_PBN_%s" % typ.upper())
        if self.rodzaj_pbn == v:
            return True
        return False

    def set_rodzaj(self, typ, value):
        warnings.warn("W przyszlosci uzyj pola 'rodzaj_pbn'", DeprecationWarning)
        v = getattr(const, "RODZAJ_PBN_%s" % typ.upper())
        if value is True:
            self.rodzaj_pbn = v
        else:
            raise NotImplementedError(
                "Nie wiem jak sie zachowac, gdy atrybut self.%s_pbn jest ustawiany na False"
                % typ
            )

    def get_artykul_pbn(self):
        return self.get_rodzaj("artykul")

    def get_ksiazka_pbn(self):
        return self.get_rodzaj("ksiazka")

    def get_rozdzial_pbn(self):
        return self.get_rodzaj("rozdzial")

    def set_artykul_pbn(self, v):
        return self.set_rodzaj("artykul", v)

    def set_ksiazka_pbn(self, v):
        return self.set_rodzaj("ksiazka", v)

    def set_rozdzial_pbn(self, v):
        return self.set_rodzaj("rozdzial", v)

    artykul_pbn = property(get_artykul_pbn, set_artykul_pbn)
    ksiazka_pbn = property(get_ksiazka_pbn, set_ksiazka_pbn)
    rozdzial_pbn = property(get_rozdzial_pbn, set_rozdzial_pbn)


@receiver(post_migrate)
def rebuild_handler(sender, **kwargs):
    # Ponieważ przechodzimy z modelu bez-MPTT na model z-MPTT, wypełniamy
    # mu defaultowe wartości dla poziomu, parents, itp. Stąd też, po migracji
    # potrzebne jest przebudowanie obiektów, aby relacje rodzic-dziecko
    # realizowane byłyprawidłowo
    if sender.name == "bpp":
        Charakter_Formalny.objects.rebuild()


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
    skrot_dla_pbn = models.CharField(
        max_length=10,
        verbose_name="Skrót dla PBN",
        help_text="""
    Skrót nazwy języka używany w plikach eksportu do PBN.""",
        blank=True,
    )

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
    ten typ KBN zostaną włączone do eksportu PBN jako artykuły""",
        default=False,
    )

    charakter_pbn = models.ForeignKey(
        Charakter_PBN,
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

    class Meta:
        verbose_name = "typ KBN"
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

"""
Małe klasy pomocnicze dla całego systemu
"""

from django.core.validators import RegexValidator
from django.db import models
from django.db.models import CASCADE, Q

from bpp import const
from bpp.kody_jezykow import WZORZEC_KODU, podtag_podstawowy
from bpp.models.abstract import ModelZNazwa, NazwaISkrot

from .charakter_formalny import *  # noqa
from .crossref_mapper import *  # noqa


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
    skrot_crossref = models.CharField(
        max_length=10,
        verbose_name="Skrót nazwy języka wg API CrossRef",
        blank=True,
        null=True,
        unique=True,
        validators=[
            RegexValidator(
                WZORZEC_KODU,
                "Podaj kod języka małymi literami, np. „en”, „de”, „uk” "
                "(ISO 639-1), ewentualnie z regionem, np. „en-GB”.",
            )
        ],
        help_text="Kod języka, pod jakim CrossRef opisuje publikacje w tym "
        "języku, np. „en”, „de”, „uk”. Wypełnij tylko wtedy, gdy różni się "
        "od pola „Kod języka wg BCP 47” — gdy to pole jest puste, język "
        "publikacji z CrossRef jest dopasowywany po kodzie BCP 47.",
    )

    pbn_uid = models.ForeignKey(
        "pbn_api.Language", null=True, blank=True, on_delete=models.SET_NULL
    )

    widoczny = models.BooleanField(default=True)

    kod_bcp47 = models.CharField(
        "Kod języka wg BCP 47",
        max_length=35,
        blank=True,
        default="",
        help_text="Kod języka w notacji BCP 47 (RFC 5646), np. „pl”, „en”, "
        "„en-GB”. Używany w eksporcie CERIF/OpenAIRE jako wartość atrybutu "
        "xml:lang; gdy pusty, elementy w tym języku zostaną wyeksportowane "
        "bez oznaczenia języka.",
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

    @classmethod
    def dla_kodu(cls, kod):
        """Język słownika dla kodu języka z CrossRef (albo z autodetekcji).

        Kolejność: „Skrót CrossRef” (jawna decyzja redakcji), potem „Kod
        języka wg BCP 47”. Region jest pomijany po obu stronach (``en-GB`` ↔
        ``en``). Gdy kod BCP 47 ma kilka języków, pierwszeństwo ma widoczny
        (ukryty nie przeszedłby walidacji formularza nowego rekordu), potem
        niższe ``pk`` — żeby wynik był deterministyczny. Brak → ``None``.
        """
        if not kod:
            return None
        kod = str(kod).strip()
        podtag = podtag_podstawowy(kod)
        if not podtag:
            return None

        jezyk = (
            cls.objects.filter(Q(skrot_crossref=kod) | Q(skrot_crossref__iexact=podtag))
            .order_by("-widoczny", "pk")
            .first()
        )
        if jezyk is not None:
            return jezyk

        return (
            cls.objects.filter(
                Q(kod_bcp47__iexact=podtag) | Q(kod_bcp47__istartswith=f"{podtag}-")
            )
            .order_by("-widoczny", "pk")
            .first()
        )


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
        limit_choices_to={"ukryty": False},
        help_text="""Wartość wybrana w tym polu zostanie użyta jako
        fallback, tzn. jeżeli dla charakteru formalnego danego rekordu nie
        określono odpowiedniego charakteru PBN, to zostanie użyta wartość
        tego pola, o ile wybrana. """,
        on_delete=CASCADE,
    )

    wliczaj_do_rankingu = models.BooleanField(default=True)

    ukryty = models.BooleanField(
        "Ukryj na listach wyboru",
        default=False,
        help_text="""Jeżeli zaznaczone, ten typ MNiSW/MEiN nie będzie
        proponowany na listach wyboru przy wprowadzaniu nowych rekordów.
        Istniejące rekordy korzystające z tej wartości pozostają bez zmian.""",
    )

    class Meta:
        verbose_name = "typ MNiSW/MEiN"
        verbose_name_plural = "typy KBN"
        ordering = ["nazwa"]
        app_label = "bpp"


class Rodzaj_Prawa_Patentowego(ModelZNazwa):
    eksportuj_jako_patent = models.BooleanField(
        "Eksportuj do CERIF jako patent",
        default=True,
        help_text="Odznacz dla praw, które nie są patentami w rozumieniu "
        "słownika COAR (np. znak towarowy). Takie rekordy nie trafią do "
        "eksportu CERIF/OpenAIRE — profil wymaga dla każdego rekordu typu "
        "z gałęzi „patent”, więc jedyną alternatywą byłoby zadeklarowanie "
        "ich patentami wbrew prawdzie.",
    )

    coar_type = models.CharField(
        "Typ COAR",
        max_length=200,
        blank=True,
        default="",
        help_text="Pełny identyfikator typu zasobu ze słownika COAR Resource "
        "Types, np. http://purl.org/coar/resource_type/c_15cd dla patentu. "
        "Używany w eksporcie CERIF/OpenAIRE; gdy pusty, patenty o tym "
        "rodzaju prawa zostaną wyeksportowane bez typu zasobu.",
    )

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

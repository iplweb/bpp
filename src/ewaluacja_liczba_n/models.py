from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models

from bpp.fields import YearField
from bpp.models.autor import Autor
from bpp.models.dyscyplina_naukowa import Dyscyplina_Naukowa
from bpp.models.uczelnia import Uczelnia

from .fields import LiczbaNField

#: Limit udziałów autora w jednym roku (art. 265 ust. 13 ustawy: maks. 4).
MAKS_UDZIALOW_ZA_ROK = 4


def okres_dla_lat(rok_min, rok_max=None):
    """Okres ewaluacji zawierający ``rok_min``; gdy takiego nie ma w bazie,
    tworzy okres ``rok_min``–``rok_max`` (wywołania z jawnie podanymi latami,
    np. z testów albo starszego kodu)."""
    from ewaluacja_common.models import OkresEwaluacji

    okres = OkresEwaluacji.objects.filter(
        rok_od__lte=rok_min, rok_do__gte=rok_min
    ).first()
    if okres is None:
        okres, _ = OkresEwaluacji.objects.get_or_create(
            rok_od=rok_min,
            defaults={"rok_do": rok_max if rok_max is not None else rok_min},
        )
    return okres


def domyslny_okres():
    """Okres domyślny (zawierający bieżący rok). Gdy tabela okresów jest pusta
    (np. po TRUNCATE w testach transakcyjnych) — zakłada okres 2022–2025,
    pierwszy obsługiwany przez system."""
    from ewaluacja_common.okres import okres_domyslny

    return okres_domyslny() or okres_dla_lat(2022, 2025)


def domyslny_okres_pk():
    """Wartość domyślna pól ``okres`` (klucz główny okresu domyślnego)."""
    return domyslny_okres().pk


def pole_okresu():
    return models.ForeignKey(
        "ewaluacja_common.OkresEwaluacji",
        on_delete=models.PROTECT,
        default=domyslny_okres_pk,
        verbose_name="okres ewaluacji",
    )


class ZOkresemQuerySet(models.QuerySet):
    def dla_okresu(self, okres):
        return self.filter(okres=okres)


class LiczbaNDlaUczelni(models.Model):
    # Auto-indeks FK redundantny: pokrywa go unique_together
    # [uczelnia, dyscyplina_naukowa, okres]
    uczelnia = models.ForeignKey(Uczelnia, on_delete=models.CASCADE, db_index=False)
    dyscyplina_naukowa = models.ForeignKey(Dyscyplina_Naukowa, on_delete=models.CASCADE)
    liczba_n = LiczbaNField()
    sankcje = LiczbaNField(
        default=0,
        help_text="Sankcje zmniejszające liczbę N dla optymalizacji",
    )
    okres = pole_okresu()

    objects = ZOkresemQuerySet.as_manager()

    class Meta:
        verbose_name = "Liczba N dla uczelni"
        verbose_name_plural = "Liczby N dla uczelni"
        unique_together = [
            ("uczelnia", "dyscyplina_naukowa", "okres"),
        ]

    def __str__(self):
        return f"{self.dyscyplina_naukowa.nazwa} -> {self.liczba_n}"

    @property
    def liczba_n_ostateczna(self):
        """Liczba 3N minus sankcje (używana w optymalizacji jako limit slotów)"""
        return max(Decimal("0"), (self.liczba_n * 3) - (self.sankcje or Decimal("0")))


class IloscUdzialowDlaAutoraBase(models.Model):
    """Abstract base model for author share calculations"""

    # Auto-indeks FK redundantny: pokrywa go unique_together z autorem jako
    # kolumną wiodącą w klasach pochodnych — IloscUdzialowDlaAutoraZaRok
    # [autor, dyscyplina_naukowa, rok] oraz IloscUdzialowDlaAutoraZaCalosc
    # [autor, dyscyplina_naukowa, rodzaj_autora, uczelnia, okres]
    autor = models.ForeignKey(Autor, on_delete=models.CASCADE, db_index=False)
    dyscyplina_naukowa = models.ForeignKey(Dyscyplina_Naukowa, on_delete=models.CASCADE)
    ilosc_udzialow = LiczbaNField()
    ilosc_udzialow_monografie = LiczbaNField()

    class Meta:
        abstract = True

    def clean(self):
        if (
            self.ilosc_udzialow is not None
            and self.ilosc_udzialow_monografie is not None
            and self.ilosc_udzialow_monografie > self.ilosc_udzialow
        ):
            raise ValidationError(
                "Ilość udziałów za monografie nie może przekraczać ilości udziałów"
            )


class IloscUdzialowDlaAutoraZaRok(IloscUdzialowDlaAutoraBase):
    """Shares for an author in a specific year"""

    rok = YearField()
    autor_dyscyplina = models.ForeignKey(
        "bpp.Autor_Dyscyplina",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Link do oryginalnego rekordu Autor_Dyscyplina za dany rok",
    )
    uczelnia = models.ForeignKey(
        "bpp.Uczelnia", on_delete=models.CASCADE, null=True, blank=True
    )

    # Override ilosc_udzialow to add validator for yearly limit
    ilosc_udzialow = LiczbaNField(validators=[MaxValueValidator(MAKS_UDZIALOW_ZA_ROK)])

    class Meta:
        verbose_name = "Ilość udziałów dla autora za rok"
        verbose_name_plural = "Ilości udziałów dla autorów za rok"
        unique_together = [
            ("autor", "dyscyplina_naukowa", "rok", "uczelnia"),
        ]


class IloscUdzialowDlaAutoraZaCalosc(IloscUdzialowDlaAutoraBase):
    """Total shares for an author across the entire evaluation period"""

    rodzaj_autora = models.ForeignKey(
        "ewaluacja_common.Rodzaj_Autora",
        on_delete=models.CASCADE,
        verbose_name="Rodzaj autora",
        null=True,
        blank=True,
    )
    uczelnia = models.ForeignKey(
        "bpp.Uczelnia", on_delete=models.CASCADE, null=True, blank=True
    )

    komentarz = models.TextField(
        blank=True,
        default="",
        help_text="Dodatkowe informacje o wyliczeniach",
    )

    okres = pole_okresu()

    objects = ZOkresemQuerySet.as_manager()

    class Meta:
        verbose_name = "Ilość udziałów dla autora za cały okres"
        verbose_name_plural = "Ilości udziałów dla autorów za cały okres"
        unique_together = [
            ("autor", "dyscyplina_naukowa", "rodzaj_autora", "uczelnia", "okres"),
        ]

    @staticmethod
    def maksymalna_ilosc_udzialow(okres):
        """Górna granica sumy udziałów za cały okres: 4 udziały na każdy rok
        okresu (2022–2025 → 16, 2026–2030 → 20)."""
        return Decimal(MAKS_UDZIALOW_ZA_ROK * okres.liczba_lat)

    def clean(self):
        super().clean()
        if self.ilosc_udzialow is None or self.okres_id is None:
            return
        maks = self.maksymalna_ilosc_udzialow(self.okres)
        if self.ilosc_udzialow > maks:
            raise ValidationError(
                {
                    "ilosc_udzialow": f"Ilość udziałów za okres {self.okres} "
                    f"nie może przekraczać {maks}."
                }
            )


class DyscyplinaNieRaportowana(models.Model):
    # Auto-indeks FK redundantny: pokrywa go unique_together
    # [uczelnia, dyscyplina_naukowa, okres]
    uczelnia = models.ForeignKey(
        "bpp.Uczelnia", on_delete=models.CASCADE, db_index=False
    )
    dyscyplina_naukowa = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa", on_delete=models.CASCADE
    )
    liczba_n = LiczbaNField(
        default=0, help_text="Liczba N dla dyscypliny (poniżej progu raportowania)"
    )
    okres = pole_okresu()

    objects = ZOkresemQuerySet.as_manager()

    class Meta:
        unique_together = [("uczelnia", "dyscyplina_naukowa", "okres")]
        verbose_name = "Dyscyplina nieraportowana"
        verbose_name_plural = "Dyscypliny nieraportowane"

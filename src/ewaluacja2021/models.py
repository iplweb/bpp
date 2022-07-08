# Create your models here.

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import JSONField
from django.urls import reverse

from import_common.core import matchuj_autora, matchuj_dyscypline
from . import const
from .fields import LiczbaNField
from .util import InputXLSX, float_or_string_or_int_or_none_to_decimal
from .validators import xlsx_header_validator

from bpp.models import Cache_Punktacja_Autora_Query
from bpp.models.autor import Autor
from bpp.models.dyscyplina_naukowa import Dyscyplina_Naukowa
from bpp.models.uczelnia import Uczelnia


def dyscypliny_naukowe_w_bazie():
    dyscypliny_z_liczba_n = LiczbaNDlaUczelni.objects.values_list(
        "dyscyplina_naukowa", flat=True
    )

    return {
        "pk__in": [
            dyscyplina
            for dyscyplina in Cache_Punktacja_Autora_Query.objects.values_list(
                "dyscyplina", flat=True
            ).distinct()
            if dyscyplina in dyscypliny_z_liczba_n
        ]
    }


class ZamowienieNaRaport(models.Model):
    rodzaj = models.CharField(
        verbose_name="Rodzaj algorytmu",
        max_length=25,
        choices=[
            ("plecakowy", "plecakowy"),
            ("plecakowy_bez_limitu", "plecakowy bez limitu na uczelnię"),
            ("genetyczny", "genetyczny"),
            ("genetyczny_z_odpinaniem", "genetyczny z odpinaniem"),
        ],
    )
    dyscyplina_naukowa = models.ForeignKey(
        Dyscyplina_Naukowa,
        on_delete=models.CASCADE,
        limit_choices_to=dyscypliny_naukowe_w_bazie,
    )
    uid_zadania = models.TextField(blank=True, null=True)
    plik_wyjsciowy = models.FileField()
    wykres_wyjsciowy = models.ImageField()

    ostatnio_zmodyfikowany = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=255, default="", blank=True, null=True)

    def get_absolute_url(self):
        return reverse("ewaluacja2021:szczegoly-raportu3n", args=(self.pk,))

    class Meta:
        ordering = ("-ostatnio_zmodyfikowany",)


class LiczbaNDlaUczelni(models.Model):
    uczelnia = models.ForeignKey(Uczelnia, on_delete=models.CASCADE)
    dyscyplina_naukowa = models.ForeignKey(Dyscyplina_Naukowa, on_delete=models.CASCADE)
    liczba_n = LiczbaNField()

    class Meta:
        verbose_name = "Liczba N dla uczelni"
        verbose_name_plural = "Liczby N dla uczelni"
        unique_together = [
            ("uczelnia", "dyscyplina_naukowa"),
        ]


class IloscUdzialowDlaAutora(models.Model):
    autor = models.ForeignKey(Autor, on_delete=models.CASCADE)
    dyscyplina_naukowa = models.ForeignKey(Dyscyplina_Naukowa, on_delete=models.CASCADE)
    ilosc_udzialow = LiczbaNField(validators=[MaxValueValidator(4)])
    ilosc_udzialow_monografie = LiczbaNField()

    class Meta:
        verbose_name = "ilość udziałów dla autora"
        verbose_name_plural = "ilości udziałów dla autorów"
        unique_together = [
            (
                "autor",
                "dyscyplina_naukowa",
            )
        ]

    def clean(self):
        if (
            self.ilosc_udzialow is not None
            and self.ilosc_udzialow_monografie is not None
            and self.ilosc_udzialow_monografie > self.ilosc_udzialow
        ):
            raise ValidationError(
                "Ilość udziałów za monografie nie może przekraczać ilości udziałów"
            )


class ImportMaksymalnychSlotow(models.Model):
    header_columns = const.IMPORT_MAKSYMALNYCH_SLOTOW_COLUMNS

    plik = models.FileField(
        validators=[
            xlsx_header_validator(header_columns),
        ]
    )

    started_on = models.DateTimeField(null=True, blank=True)
    ostatnia_zmiana = models.DateTimeField(auto_now=True)
    przeanalizowany = models.BooleanField(default=False)

    class Meta:
        ordering = ("-ostatnia_zmiana",)

    def get_absolute_url(self):
        return reverse("ewaluacja2021:szczegoly-importu", args=(self.pk,))

    def analizuj(self):
        self.wierszimportumaksymalnychslotow_set.all().delete()
        i = InputXLSX(self.plik.path, self.header_columns)
        for elem in i.rows_as_dict():

            wiersz = WierszImportuMaksymalnychSlotow(
                parent=self,
                orig_data=elem,
                matched_autor=matchuj_autora(
                    imiona=elem.get("imie"),
                    nazwisko=elem.get("nazwisko"),
                    orcid=elem.get("orcid"),
                    tytul_str=elem.get("stopien_tytul"),
                ),
                matched_dyscyplina=matchuj_dyscypline(
                    kod=None, nazwa=elem.get("dyscyplina")
                ),
            )

            wiersz.poprawny = wiersz.check_if_valid()
            if wiersz.poprawny:
                wiersz.wymagana_integracja = wiersz.check_if_integration_needed()
            wiersz.save()

        self.przeanalizowany = True
        self.save()

    def integruj(self):
        for wiersz in self.wiersze_do_integracji():
            wiersz.integruj()

    def task_perform(self):
        self.analizuj()
        self.integruj()

    def bledne_wiersze(self):
        return self.wierszimportumaksymalnychslotow_set.exclude(
            poprawny=True
        ).select_related("matched_autor", "matched_dyscyplina", "matched_autor__tytul")

    def wiersze_do_integracji(self):
        return self.wierszimportumaksymalnychslotow_set.filter(
            poprawny=True, wymagana_integracja=True
        ).exclude(zintegrowany=True)

    def wiersze_zintegrowane(self):
        return (
            self.wierszimportumaksymalnychslotow_set.filter(
                poprawny=True, wymagana_integracja=True, zintegrowany=True
            )
            .order_by("matched_autor__nazwisko", "matched_autor__imiona")
            .select_related(
                "matched_autor", "matched_dyscyplina", "matched_autor__tytul"
            )
        )

    def wiersze_nie_zintegrowane(self):
        return (
            self.wierszimportumaksymalnychslotow_set.filter(poprawny=True)
            .exclude(wymagana_integracja=True)
            .order_by("matched_autor__nazwisko", "matched_autor__imiona")
            .select_related(
                "matched_autor", "matched_dyscyplina", "matched_autor__tytul"
            )
        )


class WierszImportuMaksymalnychSlotow(models.Model):
    parent = models.ForeignKey(ImportMaksymalnychSlotow, on_delete=models.CASCADE)

    orig_data = JSONField()

    matched_autor = models.ForeignKey(
        "bpp.Autor", on_delete=models.SET_NULL, null=True, blank=True
    )
    matched_dyscyplina = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    poprawny = models.BooleanField(null=True, blank=True, default=None)
    wymagana_integracja = models.BooleanField(null=True, blank=True, default=None)
    zintegrowany = models.BooleanField(default=False)

    @property
    def ilosc_udzialow(self):
        i = self.orig_data.get(
            "maksymalna_suma_udzialow_jednostkowych_wszystkie_dyscypliny"
        )
        return float_or_string_or_int_or_none_to_decimal(i)

    @property
    def ilosc_udzialow_monografie(self):
        i = self.orig_data.get("maksymalna_suma_udzialow_jednostkowych_monografie")
        return float_or_string_or_int_or_none_to_decimal(i)

    def check_if_valid(self):
        ma_autora = self.matched_autor_id is not None
        ma_dyscypline = self.matched_dyscyplina_id is not None
        ma_udzialy = self.ilosc_udzialow is not None and self.ilosc_udzialow != 0
        ma_udzialy_mono = (
            self.ilosc_udzialow_monografie is not None
            and self.ilosc_udzialow_monografie != 0
        )
        if ma_autora and ma_dyscypline and ma_udzialy and ma_udzialy_mono:
            return True

        return False

    def istniejace_dane(self):
        return IloscUdzialowDlaAutora.objects.filter(
            autor=self.matched_autor,
            dyscyplina_naukowa=self.matched_dyscyplina,
        )

    def check_if_integration_needed(self):
        istniejace_dane = self.istniejace_dane().first()

        if istniejace_dane is not None:
            if (
                istniejace_dane.ilosc_udzialow == self.ilosc_udzialow
                and istniejace_dane.ilosc_udzialow_monografie
                == self.ilosc_udzialow_monografie
            ):
                # Wszystko już jest w bazie, integracja zbędna
                return False

        # Brak rekordu lub dane rózne
        return True

    def integruj(self):
        if not self.check_if_integration_needed():
            return

        if self.istniejace_dane().exists():
            i = self.istniejace_dane().first()
            i.ilosc_udzialow = self.ilosc_udzialow
            i.ilosc_udzialow_monografie = self.ilosc_udzialow_monografie
            i.save()
        else:
            IloscUdzialowDlaAutora.objects.create(
                autor=self.matched_autor,
                dyscyplina_naukowa=self.matched_dyscyplina,
                ilosc_udzialow=self.ilosc_udzialow,
                ilosc_udzialow_monografie=self.ilosc_udzialow_monografie,
            )

        self.zintegrowany = True
        self.save()

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Count, Q

from bpp.fields import YearField
from bpp.models import Autor, Dyscyplina_Naukowa
from long_running.models import Operation
from long_running.notification_mixins import ASGINotificationMixin


class ImportPlikuAbsencji(ASGINotificationMixin, Operation):
    plik = models.FileField(max_length=255, upload_to="protected/import_polon")
    zapisz_zmiany_do_bazy = models.BooleanField(default=False)

    def on_reset(self):
        self.wierszimportuplikuabsencji_set.all().delete()

    def perform(self):
        from .core.import_absencji import analyze_file_import_absencji

        analyze_file_import_absencji(self.plik.path, self)

    def get_details_set(self):
        return self.wierszimportuplikuabsencji_set.all()


class WierszImportuPlikuAbsencji(models.Model):
    parent = models.ForeignKey(ImportPlikuAbsencji, on_delete=models.CASCADE)
    dane_z_xls = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    nr_wiersza = models.PositiveSmallIntegerField()

    autor = models.ForeignKey(Autor, on_delete=models.SET_NULL, null=True, blank=True)
    rok = models.PositiveSmallIntegerField(null=True, blank=True)
    ile_dni = models.PositiveSmallIntegerField(null=True, blank=True)

    wymaga_zmiany = models.BooleanField(default=None, null=True, blank=True)
    rezultat = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("nr_wiersza",)


class ImportPlikuPolon(ASGINotificationMixin, Operation):
    rok = YearField()
    plik = models.FileField(max_length=255, upload_to="protected/import_polon")
    ukryj_niezmatchowanych_autorow = models.BooleanField(default=True)
    zapisz_zmiany_do_bazy = models.BooleanField(default=False)
    ignoruj_miejsce_pracy = models.BooleanField(
        default=False,
        verbose_name="Ignoruj miejsce pracy",
        help_text="Pomiń walidację pola ZATRUDNIENIE (czy zaczyna się od nazwy uczelni)",
    )
    # Multi-hosted: uczelnia, DLA której robiony jest import. Ustawiana z
    # requestu (domena→Site→Uczelnia) przy tworzeniu importu. Zawęża walidację
    # ZATRUDNIENIE, dopasowanie autora i raport niezmatchowanych do jednej
    # uczelni. ``null=True`` — zgodność wstecz ze starymi importami i single-
    # host bez rozstrzygnięcia (wtedy zachowanie jak dawniej, bez zawężenia).
    uczelnia = models.ForeignKey(
        "bpp.Uczelnia",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Uczelnia, dla której wykonywany jest import (multi-hosted).",
    )

    def on_reset(self):
        self.wierszimportuplikupolon_set.all().delete()

    def perform(self):
        from import_polon.core import analyze_file_import_polon

        analyze_file_import_polon(self.plik.path, self)

    def get_details_set(self):
        return WierszImportuPlikuPolon.objects.filter(parent=self)

    def autorzy_niezmatchowani(self):
        """Autor_Dyscyplina dla roku importu, których autora NIE było w pliku.

        Multi-hosted: gdy znana jest ``uczelnia`` importu, lista jest zawężona
        do autorów AKTUALNIE ZATRUDNIONYCH w tej uczelni (``aktualna_jednostka``
        w uczelni + jednostka ``skupia_pracownikow``). Bez tego zawężenia raport
        wyciekałby autorów innych uczelni współistniejących w bazie. Gdy
        ``uczelnia`` nieznana (stare importy / brak rozstrzygnięcia) — zachowanie
        wsteczne: wszyscy z dyscypliną dla roku, bez zawężenia.
        """
        from bpp.models import Autor_Dyscyplina

        matched_authors = (
            self.get_details_set()
            .filter(autor__isnull=False)
            .values_list("autor_id", flat=True)
        )

        qs = Autor_Dyscyplina.objects.filter(rok=self.rok)
        if self.uczelnia_id is not None:
            qs = qs.filter(autor__in=Autor.objects.aktualnie_zatrudnieni(self.uczelnia))

        return (
            qs.exclude(autor_id__in=matched_authors)
            .select_related(
                "autor", "dyscyplina_naukowa", "subdyscyplina_naukowa", "rodzaj_autora"
            )
            .annotate(
                liczba_prac=Count(
                    "autor__autorzy",
                    filter=Q(autor__autorzy__rekord__rok=self.rok),
                )
            )
            .order_by("autor__nazwisko", "autor__imiona")
        )


class WierszImportuPlikuPolon(models.Model):
    parent = models.ForeignKey(ImportPlikuPolon, on_delete=models.CASCADE)
    dane_z_xls = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    nr_wiersza = models.PositiveSmallIntegerField()

    autor = models.ForeignKey(Autor, on_delete=models.SET_NULL, null=True, blank=True)
    dyscyplina_naukowa = models.ForeignKey(
        Dyscyplina_Naukowa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    subdyscyplina_naukowa = models.ForeignKey(
        Dyscyplina_Naukowa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    rezultat = models.TextField(blank=True, default="")

    class Meta:
        ordering = ("nr_wiersza",)


class ImportPolonOverride(models.Model):
    """
    Model umożliwiający wymuszenie domyślnej logiki określania czy autor jest badawczy
    na podstawie grupy stanowisk.
    """

    grupa_stanowisk = models.CharField(
        max_length=200,
        unique=True,
        verbose_name="Grupa stanowisk",
        help_text="Nazwa grupy stanowisk z pliku POLON (np. 'Pracownik badawczo-dydaktyczny')",
    )
    jest_badawczy = models.BooleanField(
        verbose_name="Czy jest badawczy",
        help_text="Określa czy pracownik tej grupy stanowisk ma być oznaczony jako badawczy (typ B)",
    )

    class Meta:
        verbose_name = "Wymuszenie grupy stanowisk"
        verbose_name_plural = "Wymuszenia grup stanowisk"
        ordering = ("grupa_stanowisk",)

    def __str__(self):
        return f"{self.grupa_stanowisk} → {'TAK' if self.jest_badawczy else 'NIE'}"

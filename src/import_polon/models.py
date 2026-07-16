from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Count, Q
from liveops.models import LiveOperation

from bpp.fields import YearField
from bpp.models import Autor, Dyscyplina_Naukowa

# Pola stanu operacji liveops zerowane przed (po)ponownym enqueue. Zwierciadło
# ``liveops.views.RestartView.post`` (liveops inline'uje ten reset, nie wystawia
# go jako metody modelu) — trzymamy JEDNĄ kopię, żeby ``ZapiszDoBazyMixin`` nie
# zdryfował. Bez tego ``cancel_requested=True`` po anulowanym runie od razu
# ubiłby nowy przebieg.
_POLA_LIVEOPS_RESET = (
    "finished_on",
    "started_on",
    "finished_successfully",
    "cancelled",
    "cancel_requested",
    "traceback",
    "result_context",
    "current_stage",
    "stage_states",
    "log",
    "percent",
    "log_seq",
)


class _LiveopsResetMixin:
    """Wspólny ``reset_liveops_state`` dla importów POLON/absencji."""

    def reset_liveops_state(self):
        """Zeruje pola stanu operacji liveops (jak ``RestartView.post``), tak by
        kolejny ``enqueue()`` wystartował z czystym przebiegiem. NIE zapisuje
        (caller składa ``update_fields``) i NIE woła ``enqueue``. Zwraca listę
        ustawionych pól — do doklejenia w ``save(update_fields=)``."""
        self.finished_on = None
        self.started_on = None
        self.finished_successfully = False
        self.cancelled = False
        self.cancel_requested = False
        self.traceback = None
        self.result_context = None
        self.current_stage = -1
        self.stage_states = {}
        self.log = []
        self.percent = 0
        self.log_seq = 0
        return list(_POLA_LIVEOPS_RESET)


def _uruchom_import(parent, p, analyze):
    """Wspólny ``run`` dla obu importów: woła rdzeń z liveops ``Progress`` i
    finalizuje wynikiem (``total`` z wierszy-dzieci).

    ``liveops.runner._handle_error`` zapisuje traceback WYŁĄCZNIE do pola
    ``traceback`` (bez śladu na konsoli workera i bez rollbara). Owijamy
    właściwy przebieg, żeby błąd był WIDOCZNY: surowy traceback na stderr
    (konsola celery/run-site) + rollbar (konwencja bg-tasków), po czym
    re-raise — liveops i tak zapisze traceback do bazy i pokaże błąd w UI."""
    try:
        analyze(parent.plik.path, parent, p)
    except Exception:
        import sys
        import traceback as _traceback

        import rollbar

        _traceback.print_exc()
        rollbar.report_exc_info(sys.exc_info())
        raise
    p.result({"total": parent.get_details_set().count()})


class ImportPlikuAbsencji(_LiveopsResetMixin, LiveOperation):
    plik = models.FileField(max_length=255, upload_to="protected/import_polon")
    zapisz_zmiany_do_bazy = models.BooleanField(default=False)

    def on_restart(self):
        self.wierszimportuplikuabsencji_set.all().delete()

    def run(self, p):
        from .core.import_absencji import analyze_file_import_absencji

        _uruchom_import(self, p, analyze_file_import_absencji)

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


class ImportPlikuPolon(_LiveopsResetMixin, LiveOperation):
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

    def on_restart(self):
        self.wierszimportuplikupolon_set.all().delete()

    def run(self, p):
        from import_polon.core import analyze_file_import_polon

        _uruchom_import(self, p, analyze_file_import_polon)

    def get_details_set(self):
        return WierszImportuPlikuPolon.objects.filter(parent=self)

    def autorzy_niezmatchowani(self):
        """Autor_Dyscyplina dla roku importu, których autora NIE było w pliku.

        Multi-hosted: gdy znana jest ``uczelnia`` importu, lista jest zawężona
        do autorów ZWIĄZANYCH Z TĄ UCZELNIĄ przez realną jednostkę — obecnie
        LUB historycznie (``aktualna_jednostka`` albo któryś wpis
        ``Autor_Jednostka`` w uczelni, w obu przypadkach jednostka musi mieć
        ``skupia_pracownikow=True``). Jednostki obce/techniczne
        (``skupia_pracownikow=False``) NIE kwalifikują autora, nawet jeśli ich
        uczelnia to bieżąca uczelnia (lustrzana jednostka obca o nazwie naszej
        uczelni jest pomijana). Bez tego zawężenia raport wyciekałby autorów
        innych uczelni współistniejących w bazie. Gdy ``uczelnia`` nieznana
        (stare importy / brak rozstrzygnięcia) — zachowanie wsteczne: wszyscy
        z dyscypliną dla roku, bez zawężenia.
        """
        from bpp.models import Autor_Dyscyplina

        matched_authors = (
            self.get_details_set()
            .filter(autor__isnull=False)
            .values_list("autor_id", flat=True)
        )

        qs = Autor_Dyscyplina.objects.filter(rok=self.rok)
        if self.uczelnia_id is not None:
            qs = qs.filter(
                autor__in=Autor.objects.kiedykolwiek_zatrudnieni(self.uczelnia)
            )

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

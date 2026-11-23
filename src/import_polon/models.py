import logging

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Count, Q
from liveops.models import LiveOperation

from bpp.fields import YearField
from bpp.models import Autor, Dyscyplina_Naukowa

logger = logging.getLogger(__name__)

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


KOMUNIKAT_PLIK_Z_HASLEM_USUNIETY = (
    "Ze względów bezpieczeństwa danych plik zabezpieczony hasłem został "
    "usunięty z serwera zaraz po przetworzeniu, a hasło nie zostało nigdzie "
    "zapisane. Dlatego tego importu nie można zapisać do bazy ani uruchomić "
    "ponownie. Aby zapisać zmiany, utwórz nowy import, zaznacz „Zapisz zmiany "
    "do bazy” i ponownie wpisz hasło do pliku."
)

KOMUNIKAT_BRAK_PLIKU = (
    "Plik tego importu nie jest już dostępny na serwerze. Utwórz nowy import "
    "i wgraj plik ponownie."
)

NAZWA_USUNIETEGO_PLIKU_Z_HASLEM = (
    "(plik zabezpieczony hasłem — usunięty po przetworzeniu)"
)


class _LiveopsResetMixin:
    """Wspólny ``reset_liveops_state`` dla importów POLON/absencji
    oraz obsługa pliku importu (usuwanie odszyfrowanej kopii, brak pliku)."""

    @property
    def nazwa_pliku(self):
        """Nazwa pliku do wyświetlenia — także gdy plik już usunięto."""
        if self.plik:
            return self.plik.name
        if self.plik_byl_zaszyfrowany:
            return NAZWA_USUNIETEGO_PLIKU_Z_HASLEM
        return ""

    @property
    def plik_dostepny(self):
        """Czy plik importu da się jeszcze przeczytać (ponowny przebieg)."""
        if not self.plik:
            return False
        return self.plik.storage.exists(self.plik.name)

    @property
    def blokada_ponownego_przebiegu(self):
        """Import z pliku zabezpieczonego hasłem NIGDY nie jest uruchamiany
        ponownie ani zapisywany do bazy drugim przebiegiem — jego plik jest
        kasowany po pierwszym przebiegu. Decyduje sama flaga, NIE istnienie
        pliku: między ``p.result()`` a skasowaniem pliku jest okno, w którym
        plik jeszcze leży na dysku, a import jest już „zakończony"."""
        return self.plik_byl_zaszyfrowany

    @property
    def komunikat_braku_pliku(self):
        if self.plik_byl_zaszyfrowany:
            return KOMUNIKAT_PLIK_Z_HASLEM_USUNIETY
        return KOMUNIKAT_BRAK_PLIKU

    def usun_plik_jesli_byl_zaszyfrowany(self):
        """Kasuje z dysku odszyfrowaną kopię pliku, który był zabezpieczony
        hasłem, i czyści pole ``plik``. Plik bez hasła — bez zmian."""
        if not self.plik_byl_zaszyfrowany or not self.plik:
            return
        nazwa, storage = self.plik.name, self.plik.storage
        # Najpierw plik, POTEM pole: gdy storage zawiedzie, nazwa zostaje
        # w rekordzie i zadanie sprzątające ponowi próbę. Odwrotna kolejność
        # osierocałaby plik — pustego pola nikt już nie szuka.
        try:
            usun_plik_importu(storage, nazwa, pomin=self)
        except OSError:
            logger.exception(
                "Nie udało się usunąć pliku importu %s (pk=%s) — zostaje do "
                "ponownej próby przez zadanie sprzątające",
                type(self).__name__,
                self.pk,
            )
            return
        # ``update()`` zamiast ``save()``: rekord mógł zniknąć w międzyczasie.
        type(self).objects.filter(pk=self.pk).update(plik="")
        self.plik = ""

    def on_restart(self):
        """Hook liveops wołany PRZED resetem stanu — także przez centralny
        ``liveops:restart`` (przycisk „Ponów”), którego nie kontrolujemy.
        Import z pliku z hasłem odrzucamy tu, zanim cokolwiek zostanie
        skasowane: ``PermissionDenied`` daje 403, nie 500, i nie rusza wyników."""
        if self.blokada_ponownego_przebiegu:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied(KOMUNIKAT_PLIK_Z_HASLEM_USUNIETY)
        self.get_details_set().all().delete()

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
    finalizuje wynikiem (``total`` z wierszy-dzieci + to, co zwrócił rdzeń).

    Rdzeń może zwrócić dodatkowy kontekst wyniku (import POLON zwraca
    ``{"statystyki": {...}}``); import absencji nie zwraca nic, stąd ``or {}``.
    ``p.result`` NADPISUJE ``result_context`` w całości, więc scalamy w jednym
    wywołaniu.

    ``liveops.runner._handle_error`` zapisuje traceback WYŁĄCZNIE do pola
    ``traceback`` (bez śladu na konsoli workera i w monitoringu). Owijamy
    właściwy przebieg, żeby błąd był WIDOCZNY: surowy traceback na stderr
    (konsola celery/run-site) + monitoring błędów (konwencja bg-tasków), po czym
    re-raise — liveops i tak zapisze traceback do bazy i pokaże błąd w UI."""
    from bpp.wersjonowanie import jako_uzytkownik

    try:
        if not parent.plik_dostepny:
            # Ponowny przebieg (restart liveops, „Zapisz do bazy") importu,
            # którego plik usunięto — błąd użytkownika, nie aplikacji.
            p.error(parent.komunikat_braku_pliku)
            return

        try:
            # Autor wpisów historii zmienianych rekordów = właściciel importu.
            with jako_uzytkownik(parent.owner):
                wynik = analyze(parent.plik.path, parent, p)
        except Exception:
            import sys
            import traceback as _traceback

            from bpp.zglaszanie_bledow import capture_exception

            _traceback.print_exc()
            capture_exception(sys.exc_info())
            raise
        # Kasujemy PRZED oznaczeniem sukcesu — po ``p.result()`` import jest
        # „zakończony" i w UI pojawiają się akcje kolejnego przebiegu.
        parent.usun_plik_jesli_byl_zaszyfrowany()
        p.result({"total": parent.get_details_set().count(), **(wynik or {})})
    finally:
        # Odszyfrowana kopia pliku z hasłem nie zostaje na serwerze — ani po
        # sukcesie, ani po błędzie czy anulowaniu (także po podglądzie).
        parent.usun_plik_jesli_byl_zaszyfrowany()


class ImportPlikuAbsencji(_LiveopsResetMixin, LiveOperation):
    plik = models.FileField(max_length=255, upload_to="protected/import_polon")
    plik_byl_zaszyfrowany = models.BooleanField(
        default=False,
        editable=False,
        help_text=(
            "Wgrany plik był zabezpieczony hasłem; jego odszyfrowana kopia "
            "jest usuwana z serwera po przetworzeniu."
        ),
    )
    zapisz_zmiany_do_bazy = models.BooleanField(default=False)

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
    plik_byl_zaszyfrowany = models.BooleanField(
        default=False,
        editable=False,
        help_text=(
            "Wgrany plik był zabezpieczony hasłem; jego odszyfrowana kopia "
            "jest usuwana z serwera po przetworzeniu."
        ),
    )
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

    def run(self, p):
        from import_polon.core import analyze_file_import_polon

        _uruchom_import(self, p, analyze_file_import_polon)

    @property
    def nazwa_pliku_skrocona(self):
        """Nazwa pliku bez katalogu i z wyciętym środkiem — do tabeli na liście."""
        from import_polon.utils import skroc_nazwe_pliku

        return skroc_nazwe_pliku(self.nazwa_pliku)

    @property
    def statystyki(self):
        """Liczniki zapisane przez rdzeń importu (+ wartość pochodna), albo ``None``.

        ``None`` dla importów sprzed wprowadzenia statystyk oraz dla tych, które
        nie doszły do ``p.result`` (w trakcie, anulowane, zakończone błędem).
        Osobna właściwość, bo szablon nie może bezpiecznie łańcuchować po
        ``result_context``, które bywa ``None``.

        ``z_uczelni`` liczymy TUTAJ, a nie w szablonie, bo szablon Django nie ma
        arytmetyki; nie zapisujemy jej też do bazy, bo wartość pochodna
        utrwalona obok składników prędzej czy później się z nimi rozjedzie.
        """
        dane = (self.result_context or {}).get("statystyki")
        if dane is None:
            return None

        odrzuconych = dane.get("odrzuconych_zatrudnienie")
        # ``.get``, nie ``[...]``: to dane z bazy, nie inwariant kodu. Niekompletny
        # JSON (ręczna edycja, import z przyszłej wersji rdzenia) nie może wywalić
        # 500 na CAŁEJ liście — property nie jest wyciszane przez resolver szablonu.
        wierszy = dane.get("wierszy_w_pliku")
        return {
            **dane,
            # ``None`` (walidacja ZATRUDNIENIE wyłączona) propaguje się dalej —
            # szablon pokaże „n/d", a nie zmyśloną liczbę.
            "z_uczelni": (
                None
                if odrzuconych is None or wierszy is None
                else wierszy - odrzuconych
            ),
        }

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


def usun_plik_importu(storage, nazwa, pomin=None):
    """Kasuje plik importu z dysku, o ile żaden import (POLON ani absencji)
    — poza ``pomin`` — go już nie wskazuje. Jedno miejsce dla ``post_delete``
    i dla kasowania odszyfrowanej kopii po przebiegu. Zwraca True, gdy plik
    skasowano. Błąd storage (``OSError``) przechodzi do wołającego.

    Znane ograniczenie: sprawdzenie referencji i ``delete`` nie są atomowe —
    import utworzony w tej chwili z TĄ SAMĄ ścieżką straciłby plik. W kodzie
    nie ma ścieżki, która przypisuje istniejącą nazwę nowemu importowi
    (``upload_to`` nadaje unikalne nazwy), więc nie blokujemy tego dodatkowo.
    """
    if not nazwa:
        return False
    for model in (ImportPlikuPolon, ImportPlikuAbsencji):
        qs = model.objects.filter(plik=nazwa)
        if isinstance(pomin, model):
            qs = qs.exclude(pk=pomin.pk)
        if qs.exists():
            return False  # plik współdzielony z innym importem
    # ``FileSystemStorage.delete`` po cichu pomija brakujący plik.
    storage.delete(nazwa)
    return True


def _usun_plik_importu(sender, instance, **kwargs):
    """``post_delete``: kasuje plik usuniętego importu z dysku.

    Dawniej rekordy znikały (lista trzyma 10 ostatnich importów), a pliki
    zostawały w ``protected/import_polon/`` na zawsze. Plik kasujemy dopiero
    po commicie (wycofana transakcja nie zgubi pliku) i tylko wtedy, gdy żaden
    inny import nie wskazuje tej samej ścieżki.
    """
    from django.db import transaction

    nazwa = instance.plik.name if instance.plik else ""
    if not nazwa:
        return
    storage = instance.plik.storage

    transaction.on_commit(lambda: usun_plik_importu(storage, nazwa))


models.signals.post_delete.connect(
    _usun_plik_importu,
    sender=ImportPlikuPolon,
    dispatch_uid="import_polon_usun_plik_polon",
)
models.signals.post_delete.connect(
    _usun_plik_importu,
    sender=ImportPlikuAbsencji,
    dispatch_uid="import_polon_usun_plik_absencji",
)

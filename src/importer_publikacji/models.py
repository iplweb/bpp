from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from bpp import const

# Domyślny próg watchdoga sesji (sekundy). Sesja w stanie in-flight
# (FETCHING/CREATING) dłużej niż tyle jest uznawana za martwą — patrz
# ImportSession.is_stalled(). Nadpisywalny ustawieniem IMPORTER_STALL_TIMEOUT.
DEFAULT_STALL_TIMEOUT = 180


class ImportSession(models.Model):
    """Stan sesji importu publikacji."""

    class Status(models.TextChoices):
        FETCHED = "fetched", "Pobrano dane"
        FETCHING = "fetching", "Trwa pobieranie"
        CREATING = "creating", "Trwa tworzenie rekordu"
        IMPORT_FAILED = "import_failed", "Błąd importu"
        VERIFIED = "verified", "Zweryfikowano"
        SOURCE_MATCHED = "source_matched", "Dopasowano źródło"
        AUTHORS_MATCHED = (
            "authors_matched",
            "Dopasowano autorów",
        )
        PUNKTACJA = "punktacja", "Punktacja"
        REVIEW = "review", "Do przeglądu"
        COMPLETED = "completed", "Zakończono"
        CANCELLED = "cancelled", "Anulowano"

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="importer_publikacji_sessions",
        verbose_name="utworzył",
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="importer_modified_sessions",
        verbose_name="ostatnio zmodyfikował",
    )
    uczelnia = models.ForeignKey(
        "bpp.Uczelnia",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="importer_publikacji_sessions",
        verbose_name="uczelnia",
        help_text=(
            "Uczelnia hosta, z którego utworzono sesję (multi-hosted). "
            "Steruje konfiguracją PBN użytą do sprawdzenia/eksportu."
        ),
    )
    provider_name = models.CharField(
        "dostawca danych",
        max_length=50,
    )
    identifier = models.TextField(
        "identyfikator",
    )
    status = models.CharField(
        "status",
        max_length=20,
        choices=Status.choices,
        default=Status.FETCHED,
    )
    raw_data = models.JSONField(
        "dane surowe",
        help_text="Pełna odpowiedź API dostawcy",
    )
    normalized_data = models.JSONField(
        "dane znormalizowane",
        help_text="Dane FetchedPublication jako dict",
    )
    matched_data = models.JSONField(
        "dane dopasowane",
        default=dict,
        blank=True,
        help_text="Wybory użytkownika na poszczególnych etapach",
    )

    charakter_formalny = models.ForeignKey(
        "bpp.Charakter_Formalny",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="charakter formalny",
    )
    typ_kbn = models.ForeignKey(
        "bpp.Typ_KBN",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="typ KBN",
    )
    zrodlo = models.ForeignKey(
        "bpp.Zrodlo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="źródło",
    )
    wydawca = models.ForeignKey(
        "bpp.Wydawca",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="wydawca",
    )
    wydawnictwo_nadrzedne = models.ForeignKey(
        "bpp.Wydawnictwo_Zwarte",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="wydawnictwo nadrzędne",
    )
    wydawnictwo_nadrzedne_w_pbn = models.ForeignKey(
        "pbn_api.Publication",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="wydawnictwo nadrzędne w PBN",
    )
    jezyk = models.ForeignKey(
        "bpp.Jezyk",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="język",
    )
    jest_wydawnictwem_zwartym = models.BooleanField(
        "jest wydawnictwem zwartym",
        default=False,
    )

    created_record_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="typ utworzonego rekordu",
    )
    created_record_id = models.BigIntegerField(
        "ID utworzonego rekordu",
        null=True,
        blank=True,
    )
    created_record = GenericForeignKey(
        "created_record_content_type",
        "created_record_id",
    )

    created = models.DateTimeField("utworzono", auto_now_add=True)
    modified = models.DateTimeField("zmodyfikowano", auto_now=True)

    celery_task_id = models.CharField(
        "Celery task ID",
        max_length=64,
        blank=True,
        default="",
    )

    last_error_message = models.CharField(
        "Ostatni komunikat błędu",
        max_length=255,
        blank=True,
        default="",
    )

    last_error_traceback = models.TextField(
        "Pełny traceback ostatniego błędu",
        blank=True,
        default="",
    )

    last_failed_stage = models.CharField(
        "Etap który padł",
        max_length=16,
        blank=True,
        default="",
        help_text="'fetch' lub 'create'",
    )

    class Meta:
        verbose_name = "sesja importu"
        verbose_name_plural = "sesje importu"
        ordering = ["-created"]

    def __str__(self):
        return f"{self.provider_name}: {self.identifier} ({self.get_status_display()})"

    def get_continue_url(self):
        from django.urls import reverse

        status_url_map = {
            self.Status.FETCHED: "verify",
            self.Status.FETCHING: "task-status",
            self.Status.CREATING: "task-status",
            self.Status.IMPORT_FAILED: "task-status",
            self.Status.VERIFIED: "source",
            self.Status.SOURCE_MATCHED: "authors",
            self.Status.AUTHORS_MATCHED: "punktacja",
            self.Status.PUNKTACJA: "review",
            self.Status.REVIEW: "review",
            self.Status.COMPLETED: "done",
        }
        name = status_url_map.get(self.status)
        if name is None:
            return None
        return reverse(
            f"importer_publikacji:{name}",
            kwargs={"session_id": self.pk},
        )

    # Statusy "w locie": task Celery jeszcze pracuje (albo powinien). Tylko
    # dla nich watchdog może orzec zawieszenie — stan terminalny nigdy nie
    # jest "zawieszony".
    _INFLIGHT_STATUSES = (Status.FETCHING, Status.CREATING)

    def is_stalled(self, *, now=None):
        """Czy sesja tkwi w stanie in-flight (FETCHING/CREATING) dłużej niż
        próg watchdoga.

        Rozwiązuje realny defekt: gdy worker Celery zginie (SIGABRT/OOM/
        deploy) albo task nigdy nie zostanie podniesiony, blok ``except`` w
        ``fetch_session_task``/``create_publication_task`` się NIE wykona,
        więc ``status`` zostaje na zawsze w FETCHING/CREATING, a frontend
        (HTMX ``every 3s``) w kółko pokazuje "Pobieram dane od dostawcy...".
        Taki task nie rzuca łapalnego wyjątku i nie trafia do Rollbara.

        Próg liczony od ``modified`` — każdy zapis postępu odsuwa go, więc
        legalnie długi (ale żywy) import nie jest fałszywie ubijany.

        Args:
            now: bieżący czas (wstrzykiwalny w testach). Domyślnie
                ``timezone.now()``.
        """
        if self.status not in self._INFLIGHT_STATUSES:
            return False
        timeout = getattr(settings, "IMPORTER_STALL_TIMEOUT", DEFAULT_STALL_TIMEOUT)
        now = now or timezone.now()
        return (now - self.modified).total_seconds() > timeout

    def mark_stalled(self):
        """Przełącz zawieszoną sesję na IMPORT_FAILED z user-safe komunikatem.

        Ustawia ``last_failed_stage`` zgodnie z etapem in-flight (fetch/create),
        żeby istniejący ``ImportTaskRetryView`` ponowił WŁAŚCIWY task. Czyści
        ``celery_task_id`` — tak samo jak wszystkie terminalne ścieżki tasków.
        """
        stage = "fetch" if self.status == self.Status.FETCHING else "create"
        self.status = self.Status.IMPORT_FAILED
        self.last_failed_stage = stage
        self.last_error_message = (
            "Problem: operacja trwała zbyt długo lub została przerwana. "
            "Spróbuj ponownie."
        )
        self.last_error_traceback = ""
        self.celery_task_id = ""
        self.save()


class ImportedAuthor(models.Model):
    """Stan dopasowania autora w sesji importu."""

    class MatchStatus(models.TextChoices):
        AUTO_EXACT = "auto_exact", "Automatyczne dokładne"
        AUTO_LOOSE = "auto_loose", "Automatyczne luźne"
        MANUAL = "manual", "Ręczne"
        UNMATCHED = "unmatched", "Niedopasowany"

    class DyscyplinaSource(models.TextChoices):
        AUTO_JEDYNA = (
            "auto_jedyna",
            "Jedyna dyscyplina autora",
        )
        ZGLOSZENIE = (
            "zgloszenie",
            "Z aplikacji zgłoszeń publikacji",
        )
        MANUAL = "manual", "Wybór użytkownika"

    session = models.ForeignKey(
        ImportSession,
        on_delete=models.CASCADE,
        related_name="authors",
        verbose_name="sesja",
        # Auto-indeks FK redundantny: pokrywa go unique_together
        # [session, order] (session jest kolumną wiodącą).
        db_index=False,
    )
    order = models.PositiveIntegerField("kolejność")

    family_name = models.CharField("nazwisko", max_length=255, blank=True, default="")
    given_name = models.CharField("imiona", max_length=255, blank=True, default="")
    orcid = models.CharField("ORCID", max_length=50, blank=True, default="")
    # Pełen zapis "tak jak ma figurować w publikacji" — domyślnie
    # tworzony z family_name+given_name dostawcy, ale edytowalny w UI
    # (autor mógł podpisać się inaczej, np. panieńskim). Przy tworzeniu
    # rekordu publikacji trafia do ``Wydawnictwo_*_Autor.zapisany_jako``.
    zapisany_jako = models.CharField(
        "zapisane nazwisko", max_length=512, blank=True, default=""
    )

    match_status = models.CharField(
        "status dopasowania",
        max_length=20,
        choices=MatchStatus.choices,
        default=MatchStatus.UNMATCHED,
    )
    matched_autor = models.ForeignKey(
        "bpp.Autor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="dopasowany autor",
    )
    matched_jednostka = models.ForeignKey(
        "bpp.Jednostka",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="jednostka",
    )
    matched_dyscyplina = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="dyscyplina",
    )
    typ_ogolny = models.SmallIntegerField(
        "typ autora",
        choices=[
            (const.TO_AUTOR, "autor"),
            (const.TO_REDAKTOR, "redaktor"),
        ],
        default=const.TO_AUTOR,
    )
    dyscyplina_source = models.CharField(
        "źródło dyscypliny",
        max_length=20,
        choices=DyscyplinaSource.choices,
        default="",
        blank=True,
    )

    class Meta:
        verbose_name = "importowany autor"
        verbose_name_plural = "importowani autorzy"
        ordering = ["order"]
        unique_together = [("session", "order")]

    def __str__(self):
        return f"{self.family_name} {self.given_name}"

    @property
    def display_name(self):
        parts = [self.family_name, self.given_name]
        return " ".join(p for p in parts if p)


# Mapowanie technicznej etykiety strategii dopasowania na user-friendly
# tekst pokazywany w UI. Trzymane w models.py, nie w autor.py, żeby
# template-y (które importują tylko model) nie musiały sięgać do
# import_common.core.
POWOD_DISPLAY = {
    "iexact": "dokładne",
    "iexact_pierwsze_imie": "pierwsze imię",
    "polish_english": "wariant PL/EN",
}


class ImportedAuthor_Candidate(models.Model):
    """Kandydat na dopasowanie dla ``ImportedAuthor`` zwrócony przez
    ``znajdz_kandydatow_autora``.

    Materializuje listę z metadanymi (pewność, powód strategii, liczba
    publikacji) żeby UI wizardu mógł wyświetlić użytkownikowi pełny
    kontekst — który autor ma więcej publikacji, ORCID, jaką strategią
    został znaleziony.
    """

    imported_author = models.ForeignKey(
        ImportedAuthor,
        on_delete=models.CASCADE,
        related_name="candidates",
        verbose_name="importowany autor",
    )
    autor = models.ForeignKey(
        "bpp.Autor",
        on_delete=models.CASCADE,
        verbose_name="autor BPP",
    )
    pewnosc = models.FloatField("pewność")
    powod = models.CharField("powód dopasowania", max_length=32)
    publikacji_count = models.PositiveIntegerField("liczba publikacji", default=0)

    class Meta:
        verbose_name = "kandydat na autora"
        verbose_name_plural = "kandydaci na autora"
        ordering = ["-pewnosc", "-publikacji_count"]
        unique_together = [("imported_author", "autor")]

    def __str__(self):
        return f"{self.autor} ({self.pewnosc_procent}% / {self.powod_display})"

    @property
    def pewnosc_procent(self) -> int:
        return int(round(self.pewnosc * 100))

    @property
    def powod_display(self) -> str:
        return POWOD_DISPLAY.get(self.powod, self.powod)

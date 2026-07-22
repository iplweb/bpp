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

    class RodzajRekordu(models.TextChoices):
        """Docelowy model rekordu tworzonego przez ``_create_publication``.

        Trzecia wartość (``PATENT``) rozszerza dawny binarny wybór
        (``jest_wydawnictwem_zwartym``) o ``bpp.Patent`` — model, który NIE
        jest ani ``Wydawnictwo_Ciagle`` ani ``Wydawnictwo_Zwarte`` (brak
        ``typ_kbn``, ``charakter_formalny``/``jezyk`` zahardkodowane).
        Domyślnie ``CIAGLE`` — back-compat: dla sesji, które nigdy nie
        ustawiły tego pola, dispatch nadal idzie po
        ``jest_wydawnictwem_zwartym`` (patrz ``_create_publication``).
        """

        CIAGLE = "ciagle", "Wydawnictwo ciągłe"
        ZWARTE = "zwarte", "Wydawnictwo zwarte"
        PATENT = "patent", "Patent"

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
        PBN_CHECK = "pbn_check", "Sprawdzenie w PBN"
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
    rodzaj_rekordu = models.CharField(
        "rodzaj rekordu",
        max_length=10,
        choices=RodzajRekordu.choices,
        default=RodzajRekordu.CIAGLE,
        help_text=(
            "Docelowy model rekordu. Dla wartości innej niż „Patent” "
            "dispatch nadal kieruje się polem „jest wydawnictwem zwartym” "
            "(zgodność wsteczna)."
        ),
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

    zgloszenie = models.ForeignKey(
        "zglos_publikacje.Zgloszenie_Publikacji",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sesje_importu",
        verbose_name="Zgłoszenie publikacji",
        help_text=(
            "Zgłoszenie publikacji, które ten import domyka. Ustawiane "
            "jawnie (przycisk „Użyj importera”) albo automatycznie po DOI. "
            "Zadanie Celery dostaje wyłącznie id sesji — bez tego pola nie "
            "miałoby jak ustalić, które zgłoszenie oznaczyć."
        ),
    )
    zgloszenie_odrzucone_przez_operatora = models.BooleanField(
        "Operator odrzucił propozycje zgłoszeń",
        default=False,
        help_text=(
            "Operator kliknął „żadne z nich” na banerze kandydatów — "
            "baner nie pokazuje się już dla tej sesji."
        ),
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

    @property
    def kandydaci_zgloszen(self):
        """Zgłoszenia publikacji, które ta sesja importu mogłaby domknąć.

        Wyliczane przy każdym odczycie (nie cache'owane w polu) — DOI jest
        stabilne, a dzięki temu lista nie starzeje się względem stanu bazy.
        Pusta, gdy operator odrzucił propozycje („żadne z nich”).

        Importy lokalne: ``zgloszenia`` importuje modele, więc import na
        poziomie modułu zamknąłby cykl.
        """
        if self.zgloszenie_odrzucone_przez_operatora:
            from zglos_publikacje.models import Zgloszenie_Publikacji

            return Zgloszenie_Publikacji.objects.none()

        from .zgloszenia import kandydaci_dla_sesji

        return kandydaci_dla_sesji(self)

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
            # Po punktacji: dla źródeł NIE-PBN wchodzimy w krok "Sprawdź w PBN",
            # dla źródła PBN pomijamy go i idziemy prosto do przeglądu.
            self.Status.PUNKTACJA: ("review" if self.provider_name == "PBN" else "pbn"),
            self.Status.PBN_CHECK: "review",
            self.Status.REVIEW: "review",
            self.Status.COMPLETED: "done",
        }
        # Patent pomija kroki Source i PBN — wznowienie z listy/paczki nie może
        # kierować w te kroki (SourceView.post skorumpowałby sesję patentową).
        if self.rodzaj_rekordu == self.RodzajRekordu.PATENT:
            status_url_map[self.Status.VERIFIED] = "authors"
            status_url_map[self.Status.PUNKTACJA] = "review"
        name = status_url_map.get(self.status)
        if name is None:
            return None
        return reverse(
            f"importer_publikacji:{name}",
            kwargs={"session_id": self.pk},
        )

    @property
    def status_badge_class(self) -> str:
        """Klasa koloru Foundation dla etykiety statusu na liście sesji.

        Semantyka kolorów (żeby operator nie brał stanów w toku za sukces):
        - ``success`` (zielony) — TYLKO ``COMPLETED`` („Zakończono"),
        - ``alert`` (czerwony) — ``IMPORT_FAILED`` (błąd, wymaga akcji),
        - ``warning`` (pomarańcz) — aktywne przetwarzanie (FETCHING/CREATING),
        - ``secondary`` (szary) — pozostałe stany w toku (dane pobrane, ale
          wizard niedokończony: czeka na operatora).
        """
        if self.status == self.Status.COMPLETED:
            return "success"
        if self.status == self.Status.IMPORT_FAILED:
            return "alert"
        if self.status in (self.Status.FETCHING, self.Status.CREATING):
            return "warning"
        return "secondary"

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


class EntryStatus(models.TextChoices):
    PENDING = "pending", "Oczekuje"
    IN_PROGRESS = "in_progress", "W toku"
    IMPORTED = "imported", "Zaimportowano"
    FAILED = "failed", "Błąd"
    SKIPPED = "skipped", "Pominięty"
    MALFORMED = "malformed", "Uszkodzony"


class MultipleWorksImport(models.Model):
    """Paczka wielu prac wklejonych naraz (stager) — np. wielo-wpisowy BibTeX.

    Trzyma surowy wsad i N dzieci (``entries``); pojedyncza ``ImportSession``
    powstaje leniwie dopiero na żądanie importu konkretnego wpisu.
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="importer_publikacji_batches",
        verbose_name="utworzył",
    )
    uczelnia = models.ForeignKey(
        "bpp.Uczelnia",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="importer_publikacji_batches",
        verbose_name="uczelnia",
        help_text=(
            "Uczelnia hosta, z którego utworzono paczkę (multi-hosted). "
            "Steruje izolacją widoczności paczki i jej wpisów."
        ),
    )
    provider_name = models.CharField("dostawca danych", max_length=50)
    raw_input = models.TextField("surowy wsad")
    created = models.DateTimeField("utworzono", auto_now_add=True)
    modified = models.DateTimeField("zmodyfikowano", auto_now=True)

    class Meta:
        verbose_name = "import wielu prac"
        verbose_name_plural = "importy wielu prac"
        ordering = ["-created"]

    def __str__(self):
        return f"{self.provider_name}: paczka #{self.pk}"

    @property
    def progress(self) -> dict:
        entries = list(self.entries.select_related("session"))
        imported = sum(1 for e in entries if e.status == EntryStatus.IMPORTED)
        skipped = sum(1 for e in entries if e.status == EntryStatus.SKIPPED)
        total = len(entries)
        done = all(
            e.status in (EntryStatus.IMPORTED, EntryStatus.SKIPPED) for e in entries
        )
        return {
            "imported": imported,
            "skipped": skipped,
            "total": total,
            "done": done if total else False,
        }


class MultipleWorksImportEntry(models.Model):
    """Pojedynczy wpis paczki. Status jest WYLICZANY z ``session`` +
    ``skipped`` + ``parse_error`` — nie przechowujemy go, żeby nie rozjeżdżał
    się z ``ImportSession.status``."""

    parent = models.ForeignKey(
        MultipleWorksImport,
        on_delete=models.CASCADE,
        related_name="entries",
        verbose_name="paczka",
    )
    order = models.PositiveIntegerField("kolejność", default=0)
    raw_bibtex = models.TextField("pojedynczy wpis BibTeX")
    title = models.TextField("tytuł (podgląd)", blank=True, default="")
    parse_error = models.TextField("błąd parsowania", blank=True, default="")
    skipped = models.BooleanField("pominięty", default=False)
    session = models.OneToOneField(
        ImportSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batch_entry",
        verbose_name="sesja importu",
    )

    class Meta:
        verbose_name = "wpis paczki"
        verbose_name_plural = "wpisy paczki"
        ordering = ["order"]

    def __str__(self):
        return f"#{self.order}: {self.title or '(bez tytułu)'}"

    @property
    def status(self) -> str:
        session = self.session
        if session is not None and session.status == ImportSession.Status.COMPLETED:
            return EntryStatus.IMPORTED
        if self.skipped:
            return EntryStatus.SKIPPED
        if self.parse_error:
            return EntryStatus.MALFORMED
        if session is None:
            return EntryStatus.PENDING
        if session.status == ImportSession.Status.IMPORT_FAILED or session.is_stalled():
            return EntryStatus.FAILED
        if session.status == ImportSession.Status.CANCELLED:
            return EntryStatus.PENDING
        return EntryStatus.IN_PROGRESS

    @property
    def status_label(self) -> str:
        return EntryStatus(self.status).label

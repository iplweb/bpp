from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from bpp.models.profile import BppUser


class NotADuplicate(models.Model):
    autor = models.OneToOneField(
        "bpp.Autor",
        db_index=True,
        help_text="Primary key of the Scientist record that is NOT a duplicate",
        on_delete=models.CASCADE,
    )
    created_on = models.DateTimeField("Created on", default=timezone.now)
    created_by = models.ForeignKey(
        BppUser,
        on_delete=models.CASCADE,
        verbose_name="Created by",
        help_text="User who marked this scientist as not a duplicate",
    )

    class Meta:
        verbose_name = "Oznaczony jako nie-duplikat"
        verbose_name_plural = "Oznaczeni jako nie-duplikaty"
        ordering = ["-created_on"]

    def __str__(self):
        return f"Autor {self.autor} (not duplicate) - {self.created_by}"


class IgnoredAuthor(models.Model):
    """Authors that should be completely ignored in the deduplication process"""

    scientist = models.OneToOneField(
        "pbn_api.Scientist",
        on_delete=models.CASCADE,
        db_index=True,
        verbose_name="Scientist (PBN)",
        help_text="Scientist record that should be ignored in deduplication",
    )

    autor = models.ForeignKey(
        "bpp.Autor",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Autor (BPP)",
        help_text="Optional reference to BPP author",
    )

    reason = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Powód ignorowania",
        help_text="Opcjonalny powód dlaczego autor jest ignorowany",
    )

    created_on = models.DateTimeField("Data utworzenia", default=timezone.now)
    created_by = models.ForeignKey(
        BppUser,
        on_delete=models.CASCADE,
        verbose_name="Utworzył",
        help_text="Użytkownik który oznaczył autora jako ignorowany",
    )

    class Meta:
        verbose_name = "Ignorowany autor"
        verbose_name_plural = "Ignorowani autorzy"
        ordering = ["-created_on"]

    def __str__(self):
        if self.autor:
            return f"Ignorowany: {self.autor} (Scientist #{self.scientist.pk})"
        return f"Ignorowany: Scientist #{self.scientist.pk}"


class LogScalania(models.Model):
    """Log of author merge operations with detailed tracking"""

    # Main author (target of the merge)
    main_autor = models.ForeignKey(
        "bpp.Autor",
        on_delete=models.SET_NULL,
        null=True,
        related_name="merge_logs_as_main",
        verbose_name="Autor główny (BPP)",
        help_text="Główny autor BPP do którego przypisano publikacje",
    )

    # Duplicate author (source of the merge) - stored as CharField since it gets deleted
    duplicate_autor_str = models.CharField(
        max_length=500,
        verbose_name="Autor duplikat (tekst)",
        help_text="Tekstowa reprezentacja usuniętego autora duplikatu",
    )

    duplicate_autor_id = models.IntegerField(
        verbose_name="ID autora duplikatu",
        help_text="ID usuniętego autora duplikatu (do celów audytu)",
    )

    # PBN Scientist references (optional)
    main_scientist = models.ForeignKey(
        "pbn_api.Scientist",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merge_logs_as_main_scientist",
        verbose_name="Główny Scientist (PBN)",
        help_text="Główny rekord Scientist z PBN",
    )

    duplicate_scientist = models.ForeignKey(
        "pbn_api.Scientist",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merge_logs_as_duplicate_scientist",
        verbose_name="Duplikat Scientist (PBN)",
        help_text="Duplikat rekordu Scientist z PBN",
    )

    # Modified record tracking using GenericForeignKey
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Typ rekordu",
    )
    object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="ID rekordu",
    )
    modified_record = GenericForeignKey("content_type", "object_id")

    # Discipline tracking
    dyscyplina_before = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merge_logs_before",
        verbose_name="Dyscyplina przed",
        help_text="Dyscyplina naukowa przed scaleniem",
    )

    dyscyplina_after = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merge_logs_after",
        verbose_name="Dyscyplina po",
        help_text="Dyscyplina naukowa po scaleniu",
    )

    # Operation metadata
    operation_type = models.CharField(
        max_length=50,
        choices=[
            ("PUBLICATION_TRANSFER", "Przeniesienie publikacji"),
            ("DISCIPLINE_TRANSFER", "Przeniesienie dyscypliny"),
            ("DISCIPLINE_REMOVED", "Usunięcie dyscypliny"),
            ("AUTHOR_DELETED", "Usunięcie autora"),
        ],
        verbose_name="Typ operacji",
    )

    operation_details = models.TextField(
        blank=True,
        verbose_name="Szczegóły operacji",
        help_text="Dodatkowe informacje o operacji",
    )

    # Audit fields
    created_on = models.DateTimeField("Data utworzenia", default=timezone.now)
    created_by = models.ForeignKey(
        BppUser,
        on_delete=models.CASCADE,
        verbose_name="Wykonał",
        help_text="Użytkownik który wykonał scalanie",
    )

    # Additional tracking
    publications_transferred = models.PositiveIntegerField(
        default=0,
        verbose_name="Liczba przeniesionych publikacji",
    )

    disciplines_transferred = models.PositiveIntegerField(
        default=0,
        verbose_name="Liczba przeniesionych dyscyplin",
    )

    warnings = models.TextField(
        blank=True,
        verbose_name="Ostrzeżenia",
        help_text="Ostrzeżenia powstałe podczas scalania",
    )

    class Meta:
        verbose_name = "Log scalania autorów"
        verbose_name_plural = "Logi scalania autorów"
        ordering = ["-created_on"]
        indexes = [
            models.Index(fields=["main_autor", "created_on"]),
            models.Index(fields=["created_by", "created_on"]),
            models.Index(fields=["operation_type", "created_on"]),
        ]

    def __str__(self):
        return (
            f"{self.operation_type}: {self.duplicate_autor_str} → {self.main_autor} "
            f"({self.created_on.strftime('%Y-%m-%d %H:%M')})"
        )


class DuplicateScanRun(models.Model):
    """Represents a single scan operation for finding author duplicates."""

    class Status(models.TextChoices):
        PENDING = "pending", "Oczekuje"
        RUNNING = "running", "W trakcie"
        COMPLETED = "completed", "Zakończone"
        CANCELLED = "cancelled", "Anulowane"
        FAILED = "failed", "Błąd"

    started_at = models.DateTimeField("Rozpoczęto", auto_now_add=True)
    finished_at = models.DateTimeField("Zakończono", null=True, blank=True)
    status = models.CharField(
        "Status",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_by = models.ForeignKey(
        BppUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Utworzył",
        help_text="Użytkownik który uruchomił skanowanie (null dla zadań automatycznych)",
    )

    # Progress tracking
    total_authors_to_scan = models.PositiveIntegerField(
        "Autorów do przeskanowania",
        default=0,
    )
    authors_scanned = models.PositiveIntegerField(
        "Przeskanowano autorów",
        default=0,
    )
    duplicates_found = models.PositiveIntegerField(
        "Znaleziono duplikatów",
        default=0,
    )

    # Error tracking
    error_message = models.TextField(
        "Komunikat błędu",
        blank=True,
    )

    # Celery task ID for cancellation
    celery_task_id = models.CharField(
        "ID zadania Celery",
        max_length=255,
        blank=True,
    )

    class Meta:
        verbose_name = "Skanowanie duplikatów"
        verbose_name_plural = "Skanowania duplikatów"
        ordering = ["-started_at"]

    def __str__(self):
        return f"Skanowanie #{self.pk} ({self.get_status_display()}) - {self.started_at.strftime('%Y-%m-%d %H:%M')}"

    @property
    def progress_percent(self):
        """Returns progress as percentage (0-100)."""
        if self.total_authors_to_scan == 0:
            return 0
        return round((self.authors_scanned / self.total_authors_to_scan) * 100, 1)


class DuplicateCandidate(models.Model):
    """Stores a potential duplicate pair found during scanning."""

    class Status(models.TextChoices):
        PENDING = "pending", "Do sprawdzenia"
        MERGED = "merged", "Scalony"
        NOT_DUPLICATE = "not_duplicate", "Nie jest duplikatem"

    scan_run = models.ForeignKey(
        DuplicateScanRun,
        on_delete=models.CASCADE,
        related_name="candidates",
        verbose_name="Skanowanie",
    )

    # The main author (from OsobaZInstytucji/pbn_uid)
    main_autor = models.ForeignKey(
        "bpp.Autor",
        on_delete=models.CASCADE,
        related_name="duplicate_main_candidates",
        verbose_name="Autor główny",
    )
    main_osoba_z_instytucji = models.ForeignKey(
        "pbn_api.OsobaZInstytucji",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="OsobaZInstytucji",
    )

    # The potential duplicate
    duplicate_autor = models.ForeignKey(
        "bpp.Autor",
        on_delete=models.CASCADE,
        related_name="duplicate_candidates",
        verbose_name="Potencjalny duplikat",
    )

    # Analysis results
    confidence_score = models.IntegerField(
        "Wynik pewności",
        help_text="Surowy wynik pewności (-115 do 250)",
        db_index=True,
    )
    confidence_percent = models.FloatField(
        "Pewność (%)",
        help_text="Znormalizowany wynik (0.0 do 1.0)",
    )
    reasons = models.JSONField(
        "Powody dopasowania",
        default=list,
        help_text="Lista powodów dopasowania",
    )

    # Priority for sorting (100 = 2022-2025 with disciplines, 50 = 2022-2025, 0 = other)
    priority = models.IntegerField(
        "Priorytet",
        default=0,
        db_index=True,
        help_text="Priorytet wyświetlania: 100=prace 2022-2025 z dyscyplinami, 50=prace 2022-2025, 0=inne",
    )

    # Status tracking
    status = models.CharField(
        "Status",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    reviewed_at = models.DateTimeField(
        "Data sprawdzenia",
        null=True,
        blank=True,
    )
    reviewed_by = models.ForeignKey(
        BppUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_duplicates",
        verbose_name="Sprawdził",
    )

    # Metadata cached at scan time (for display without extra queries)
    main_autor_name = models.CharField(
        "Nazwa autora głównego",
        max_length=1024,
    )
    duplicate_autor_name = models.CharField(
        "Nazwa duplikatu",
        max_length=1024,
    )
    main_publications_count = models.PositiveIntegerField(
        "Publikacje autora głównego",
        default=0,
    )
    duplicate_publications_count = models.PositiveIntegerField(
        "Publikacje duplikatu",
        default=0,
    )

    created_at = models.DateTimeField("Utworzono", auto_now_add=True)

    class Meta:
        verbose_name = "Kandydat na duplikat"
        verbose_name_plural = "Kandydaci na duplikaty"
        ordering = ["-priority", "-confidence_score", "main_autor__nazwisko"]
        indexes = [
            models.Index(fields=["scan_run", "status"]),
            models.Index(fields=["main_autor", "status"]),
            models.Index(fields=["priority", "confidence_score"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["scan_run", "main_autor", "duplicate_autor"],
                name="unique_scan_main_duplicate",
            ),
        ]

    def __str__(self):
        return (
            f"{self.main_autor_name} ↔ {self.duplicate_autor_name} "
            f"({self.confidence_percent:.0%})"
        )

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from bpp.models.profile import BppUser


class PublicationDuplicateScanRun(models.Model):
    """Represents a single scan operation for finding publication duplicates."""

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
        help_text="Użytkownik który uruchomił skanowanie",
    )

    # Year range filter
    year_from = models.PositiveIntegerField(
        "Rok od",
        default=2022,
        help_text="Początek zakresu lat do skanowania",
    )
    year_to = models.PositiveIntegerField(
        "Rok do",
        default=2025,
        help_text="Koniec zakresu lat do skanowania",
    )

    # Ignore options
    ignore_doi = models.BooleanField(
        "Ignoruj DOI",
        default=False,
        help_text="Nie używaj DOI do porównywania",
    )
    ignore_www = models.BooleanField(
        "Ignoruj WWW",
        default=False,
        help_text="Nie używaj adresów WWW do porównywania",
    )
    ignore_isbn = models.BooleanField(
        "Ignoruj ISBN",
        default=False,
        help_text="Nie używaj ISBN do porównywania",
    )
    ignore_zrodlo = models.BooleanField(
        "Ignoruj źródło",
        default=False,
        help_text="Nie używaj źródła do porównywania",
    )

    # Progress tracking
    total_publications_to_scan = models.PositiveIntegerField(
        "Publikacji do przeskanowania",
        default=0,
    )
    publications_scanned = models.PositiveIntegerField(
        "Przeskanowano publikacji",
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
        verbose_name = "Skanowanie duplikatów publikacji"
        verbose_name_plural = "Skanowania duplikatów publikacji"
        ordering = ["-started_at"]

    def __str__(self):
        return (
            f"Skanowanie #{self.pk} ({self.get_status_display()}) - "
            f"{self.started_at.strftime('%Y-%m-%d %H:%M')}"
        )

    @property
    def progress_percent(self):
        """Returns progress as percentage (0-100)."""
        if self.total_publications_to_scan == 0:
            return 0
        return round(
            (self.publications_scanned / self.total_publications_to_scan) * 100, 1
        )


class PublicationDuplicateCandidate(models.Model):
    """Stores a potential duplicate publication pair found during scanning."""

    class Status(models.TextChoices):
        PENDING = "pending", "Do sprawdzenia"
        CONFIRMED = "confirmed", "Potwierdzony duplikat"
        NOT_DUPLICATE = "not_duplicate", "Nie jest duplikatem"

    scan_run = models.ForeignKey(
        PublicationDuplicateScanRun,
        on_delete=models.CASCADE,
        related_name="candidates",
        verbose_name="Skanowanie",
    )

    # Original publication (using GenericForeignKey)
    original_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="publication_duplicate_originals",
        verbose_name="Typ oryginalnej publikacji",
    )
    original_object_id = models.PositiveIntegerField(
        verbose_name="ID oryginalnej publikacji",
    )
    original_publication = GenericForeignKey(
        "original_content_type", "original_object_id"
    )

    # Duplicate publication (using GenericForeignKey)
    duplicate_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="publication_duplicate_duplicates",
        verbose_name="Typ duplikatu publikacji",
    )
    duplicate_object_id = models.PositiveIntegerField(
        verbose_name="ID duplikatu publikacji",
    )
    duplicate_publication = GenericForeignKey(
        "duplicate_content_type", "duplicate_object_id"
    )

    # Analysis results
    similarity_score = models.FloatField(
        "Wynik podobieństwa",
        help_text="Wynik podobieństwa (0.0 do 1.0)",
        db_index=True,
    )
    match_reasons = models.JSONField(
        "Powody dopasowania",
        default=list,
        help_text="Lista powodów dopasowania (np. 'DOI', 'tytuł', 'ISBN')",
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
        related_name="reviewed_publication_duplicates",
        verbose_name="Sprawdził",
    )

    # Cached metadata for display without extra queries
    original_title = models.CharField(
        "Tytuł oryginału",
        max_length=2048,
    )
    duplicate_title = models.CharField(
        "Tytuł duplikatu",
        max_length=2048,
    )
    original_year = models.PositiveIntegerField(
        "Rok oryginału",
        null=True,
        blank=True,
    )
    duplicate_year = models.PositiveIntegerField(
        "Rok duplikatu",
        null=True,
        blank=True,
    )
    original_type = models.CharField(
        "Typ oryginału",
        max_length=100,
        help_text="Nazwa modelu (np. 'Wydawnictwo_Ciagle')",
    )
    duplicate_type = models.CharField(
        "Typ duplikatu",
        max_length=100,
        help_text="Nazwa modelu (np. 'Wydawnictwo_Zwarte')",
    )

    created_at = models.DateTimeField("Utworzono", auto_now_add=True)

    class Meta:
        verbose_name = "Kandydat na duplikat publikacji"
        verbose_name_plural = "Kandydaci na duplikaty publikacji"
        ordering = ["-similarity_score", "original_title"]
        indexes = [
            models.Index(fields=["scan_run", "status"]),
            models.Index(fields=["similarity_score"]),
            models.Index(
                fields=["original_content_type", "original_object_id", "status"]
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "scan_run",
                    "original_content_type",
                    "original_object_id",
                    "duplicate_content_type",
                    "duplicate_object_id",
                ],
                name="unique_pub_scan_original_duplicate",
            ),
        ]

    def __str__(self):
        return (
            f"{self.original_title[:50]}... ↔ {self.duplicate_title[:50]}... "
            f"({self.similarity_score:.0%})"
        )

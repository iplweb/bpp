from django.db import models

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

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

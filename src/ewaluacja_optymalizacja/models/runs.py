"""Modele związane z pojedynczymi przebiegami optymalizacji.

Zawiera modele opisujące metadane runa optymalizacji oraz agregaty per-autor
wraz z listą publikacji wybranych do wyniku optymalizacji.
"""

from django.db import models
from django.urls import reverse

from bpp.models import Autor, Dyscyplina_Naukowa, Uczelnia
from bpp.models.fields import TupleField
from ewaluacja_common.models import Rodzaj_Autora


class OptimizationRun(models.Model):
    """
    Stores metadata about each optimization run.
    Tracks when optimization was performed and overall results.
    """

    STATUS_CHOICES = [
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    dyscyplina_naukowa = models.ForeignKey(
        Dyscyplina_Naukowa,
        on_delete=models.CASCADE,
        verbose_name="Dyscyplina naukowa",
        # Indeks pojedynczy zbędny: pokrywa go złożony
        # Index(["dyscyplina_naukowa", "-started_at"]) w Meta (kolumna wiodąca).
        db_index=False,
    )
    uczelnia = models.ForeignKey(
        Uczelnia,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Uczelnia",
        help_text="Uczelnia dla której wykonano optymalizację (opcjonalne dla pojedynczych dyscyplin)",
    )

    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Rozpoczęto")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="Zakończono")

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="running", verbose_name="Status"
    )

    # Overall statistics
    total_points = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        default=0,
        verbose_name="Suma punktów",
    )
    total_slots = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        default=0,
        verbose_name="Suma slotów",
    )
    total_publications = models.IntegerField(
        default=0, verbose_name="Liczba publikacji"
    )

    low_mono_count = models.IntegerField(
        default=0, verbose_name="Liczba nisko punktowanych monografii"
    )
    low_mono_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Procent nisko punktowanych monografii",
    )

    validation_passed = models.BooleanField(
        default=True, verbose_name="Walidacja przeszła pomyślnie"
    )

    is_optimal = models.BooleanField(
        default=True,
        verbose_name="Rozwiązanie optymalne",
        help_text="False jeśli solver zwrócił rozwiązanie dopuszczalne ale nieoptymalne "
        "(np. z powodu timeout)",
    )

    optimality_gap = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Luka optymalizacyjna (%)",
        help_text="Różnica procentowa między znalezionym rozwiązaniem a teoretycznym "
        "maksimum. Wartość 0% oznacza rozwiązanie optymalne. Null jeśli niedostępne.",
    )

    best_bound = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Teoretyczna górna granica punktów",
        help_text="Teoretyczne maksimum punktów obliczone przez solver. "
        "Null jeśli niedostępne.",
    )

    # Additional metadata
    notes = models.TextField(blank=True, default="", verbose_name="Notatki")

    class Meta:
        app_label = "ewaluacja_optymalizacja"
        verbose_name = "Wynik optymalizacji"
        verbose_name_plural = "Wyniki optymalizacji"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["-started_at"]),
            models.Index(fields=["dyscyplina_naukowa", "-started_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.dyscyplina_naukowa.nazwa} - {self.started_at.strftime('%Y-%m-%d %H:%M')}"

    def get_absolute_url(self):
        return reverse("ewaluacja_optymalizacja:run-detail", kwargs={"pk": self.pk})


class OptimizationAuthorResult(models.Model):
    """
    Stores per-author results within an optimization run.
    """

    optimization_run = models.ForeignKey(
        OptimizationRun,
        on_delete=models.CASCADE,
        related_name="author_results",
        verbose_name="Wynik optymalizacji",
        # Auto-indeks FK redundantny: unique_together (optimization_run, autor)
        # ma optimization_run jako kolumnę wiodącą — obsługuje i lookup, i kaskadę.
        db_index=False,
    )
    autor = models.ForeignKey(Autor, on_delete=models.CASCADE, verbose_name="Autor")
    rodzaj_autora = models.ForeignKey(
        Rodzaj_Autora,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Rodzaj autora",
        help_text="Określa czy autor jest w liczbie N",
    )

    # Results
    total_points = models.DecimalField(
        max_digits=20, decimal_places=4, default=0, verbose_name="Suma punktów"
    )
    total_slots = models.DecimalField(
        max_digits=20, decimal_places=4, default=0, verbose_name="Suma slotów"
    )
    mono_slots = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        default=0,
        verbose_name="Sloty monografii",
    )

    # Limits used for this author
    slot_limit_total = models.DecimalField(
        max_digits=20, decimal_places=4, verbose_name="Limit slotów (ogółem)"
    )
    slot_limit_mono = models.DecimalField(
        max_digits=20, decimal_places=4, verbose_name="Limit slotów (monografie)"
    )

    class Meta:
        app_label = "ewaluacja_optymalizacja"
        verbose_name = "Wynik autora w optymalizacji"
        verbose_name_plural = "Wyniki autorów w optymalizacji"
        ordering = ["optimization_run", "autor__nazwisko", "autor__imiona"]
        unique_together = [("optimization_run", "autor")]
        # Brak Meta.indexes: Index(["optimization_run","autor"]) duplikował
        # indeks z unique_together, a Index(["autor"]) — auto-indeks FK autor.

    def __str__(self):
        return f"{self.autor} - {self.optimization_run}"


class OptimizationPublication(models.Model):
    """
    Stores individual publications selected for each author in an optimization run.
    """

    KIND_CHOICES = [
        ("article", "Artykuł"),
        ("monography", "Monografia"),
    ]

    author_result = models.ForeignKey(
        OptimizationAuthorResult,
        on_delete=models.CASCADE,
        related_name="publications",
        verbose_name="Wynik autora",
    )

    rekord_id = TupleField(
        models.IntegerField(),
        size=2,
        db_index=True,
        verbose_name="ID rekordu (content_type_id, object_id)",
    )

    kind = models.CharField(max_length=20, choices=KIND_CHOICES, verbose_name="Rodzaj")

    points = models.DecimalField(max_digits=20, decimal_places=4, verbose_name="Punkty")
    slots = models.DecimalField(max_digits=20, decimal_places=4, verbose_name="Sloty")

    is_low_mono = models.BooleanField(
        default=False, verbose_name="Nisko punktowana monografia (< 200 pkt)"
    )

    author_count = models.IntegerField(
        default=1,
        verbose_name="Liczba autorów z przypiętymi dyscyplinami",
    )

    class Meta:
        app_label = "ewaluacja_optymalizacja"
        verbose_name = "Publikacja w optymalizacji"
        verbose_name_plural = "Publikacje w optymalizacji"
        ordering = ["author_result", "-points"]
        # Brak Meta.indexes: Index(["author_result"]) duplikował auto-indeks FK,
        # a Index(["rekord_id"]) — indeks z db_index=True na polu rekord_id.

    def __str__(self):
        return f"{self.get_kind_display()} - {self.points} pkt - {self.author_result.autor}"

    @property
    def efficiency(self):
        """Points per slot ratio"""
        return float(self.points) / float(self.slots) if self.slots > 0 else 0

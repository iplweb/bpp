from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.functions import Greatest, Least
from django.urls import reverse
from liveops.models import LiveOperation

User = get_user_model()


class NotADuplicate(models.Model):
    """Oznacza parę źródeł jako 'to nie jest duplikat'"""

    zrodlo = models.ForeignKey(
        "bpp.Zrodlo", on_delete=models.CASCADE, related_name="not_duplicate_main"
    )
    duplikat = models.ForeignKey(
        "bpp.Zrodlo", on_delete=models.CASCADE, related_name="not_duplicate_duplicate"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notaduplicate_zrodlo_set",
    )
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("zrodlo", "duplikat")]
        verbose_name = "oznaczenie 'to nie duplikat'"
        verbose_name_plural = "oznaczenia 'to nie duplikat'"
        ordering = ["-created_on"]

    def __str__(self):
        return f"{self.zrodlo} ≠ {self.duplikat}"


class IgnoredSource(models.Model):
    """Źródła wykluczone z procesu deduplikacji"""

    zrodlo = models.OneToOneField(
        "bpp.Zrodlo", on_delete=models.CASCADE, related_name="ignored_in_dedup"
    )
    reason = models.TextField(blank=True, help_text="Powód wykluczenia z deduplikacji")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ignoredsource_zrodlo_set",
    )
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "źródło ignorowane w deduplikacji"
        verbose_name_plural = "źródła ignorowane w deduplikacji"
        ordering = ["-created_on"]

    def __str__(self):
        return f"Ignorowane: {self.zrodlo}"


class ScanZrodelForDuplicates(LiveOperation):
    """Skan bazy w poszukiwaniu duplikatów źródeł (django-liveops).

    Sam rekord skanu (dziedziczy owner/timestamps/stan/result_context po
    LiveOperation). run() deleguje do operations.perform_scan.
    """

    total_sources = models.PositiveIntegerField("Źródeł do przeskanowania", default=0)
    sources_scanned = models.PositiveIntegerField("Przeskanowano źródeł", default=0)
    duplicates_found = models.PositiveIntegerField("Znaleziono duplikatów", default=0)

    class Meta:
        verbose_name = "Skanowanie duplikatów źródeł"
        verbose_name_plural = "Skanowania duplikatów źródeł"
        ordering = ["-created_on"]

    def __str__(self):
        return f"Skanowanie źródeł #{self.pk} ({self.get_state()})"

    @property
    def live_title(self):
        return "Skanowanie duplikatów źródeł"

    def run(self, p):
        from .operations import perform_scan

        perform_scan(self, p)

    def get_success_url(self):
        # Po sukcesie liveops.js robi window.location.assign(success_url) →
        # automatyczne przejście na listę duplikatów.
        return reverse("deduplikator_zrodel:duplicate_sources")

    def on_restart(self):
        # Hook RestartView: przed re-enqueue skasuj kandydatów poprzedniego
        # biegu (perform_scan i tak czyści na wejściu — to pas i szelki).
        self.candidates.all().delete()


class SourceDuplicateCandidate(models.Model):
    """Trwała para potencjalnych duplikatów znaleziona podczas skanu.

    Lżejsza niż odpowiednik z deduplikator_autorow — źródła nie są masowo
    kasowane, więc lista i XLSX renderują przez select_related zamiast grubego
    snapshotu. Cache'ujemy tylko nazwy (fallback) + liczby publikacji.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Do sprawdzenia"
        SKIPPED = "skipped", "Odłożony na później"
        MERGED = "merged", "Przemapowany/scalony"

    scan = models.ForeignKey(
        ScanZrodelForDuplicates,
        on_delete=models.CASCADE,
        related_name="candidates",
        verbose_name="Skanowanie",
    )
    main_zrodlo = models.ForeignKey(
        "bpp.Zrodlo",
        on_delete=models.CASCADE,
        related_name="dup_candidate_as_main",
        verbose_name="Źródło główne",
    )
    duplicate_zrodlo = models.ForeignKey(
        "bpp.Zrodlo",
        on_delete=models.CASCADE,
        related_name="dup_candidate_as_duplicate",
        verbose_name="Potencjalny duplikat",
    )
    confidence_score = models.IntegerField("Wynik pewności", db_index=True)

    # Cache do wyświetlania wiersza MERGED, gdy źródło zniknie tuż przed
    # renderem. Bieżące dane (issn/pbn/slug) czytane na żywo przez select_related.
    main_nazwa = models.CharField("Nazwa źródła głównego", max_length=1024, blank=True)
    duplicate_nazwa = models.CharField("Nazwa duplikatu", max_length=1024, blank=True)
    main_pub_count = models.PositiveIntegerField(
        "Publikacje źródła głównego", default=0
    )
    duplicate_pub_count = models.PositiveIntegerField("Publikacje duplikatu", default=0)

    status = models.CharField(
        "Status",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    reviewed_at = models.DateTimeField("Data rozpatrzenia", null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Rozpatrzył",
    )
    created_at = models.DateTimeField("Utworzono", auto_now_add=True)

    class Meta:
        verbose_name = "Kandydat na duplikat źródła"
        verbose_name_plural = "Kandydaci na duplikaty źródeł"
        ordering = ["-confidence_score"]
        indexes = [models.Index(fields=["scan", "status"])]
        constraints = [
            # Nieuporządkowana para w obrębie skanu — twardy backstop
            # niezależny od kanonikalizacji w kodzie (zależnej od pub_count).
            models.UniqueConstraint(
                Least("main_zrodlo", "duplicate_zrodlo"),
                Greatest("main_zrodlo", "duplicate_zrodlo"),
                "scan",
                name="uniq_scan_unordered_pair",
            ),
        ]

    def __str__(self):
        return f"{self.main_nazwa} ↔ {self.duplicate_nazwa} ({self.confidence_score})"

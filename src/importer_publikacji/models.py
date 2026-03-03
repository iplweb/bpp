from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class ImportSession(models.Model):
    """Stan sesji importu publikacji."""

    class Status(models.TextChoices):
        FETCHED = "fetched", "Pobrano dane"
        VERIFIED = "verified", "Zweryfikowano"
        SOURCE_MATCHED = "source_matched", "Dopasowano źródło"
        AUTHORS_MATCHED = (
            "authors_matched",
            "Dopasowano autorów",
        )
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
    provider_name = models.CharField(
        "dostawca danych",
        max_length=50,
    )
    identifier = models.CharField(
        "identyfikator",
        max_length=255,
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
            self.Status.VERIFIED: "source",
            self.Status.SOURCE_MATCHED: "authors",
            self.Status.AUTHORS_MATCHED: "review",
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
    )
    order = models.PositiveIntegerField("kolejność")

    family_name = models.CharField("nazwisko", max_length=255, blank=True, default="")
    given_name = models.CharField("imiona", max_length=255, blank=True, default="")
    orcid = models.CharField("ORCID", max_length=50, blank=True, default="")

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

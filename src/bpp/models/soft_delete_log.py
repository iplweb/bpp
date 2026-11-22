"""Dedykowany audyt operacji soft-delete (kto / kiedy / dlaczego / PBN).

DLACZEGO OSOBNY MODEL, SKORO JEST ``django-easy-audit``: easy-audit
zapisuje ZMIANY PÓL, więc soft-delete widzi jako „``deleted_at``: null →
2026-08-16" — bez powodu, bez związku ze zleceniem wycofania z PBN i bez
odpowiedzi na pytanie „co jeszcze poszło do kosza tą samą decyzją".
Ten model odpowiada na pytania operacyjne: kto usunął, dlaczego, czy
oświadczenia wyjechały z PBN i pod jakim wpisem kolejki.

DLACZEGO GFK, A NIE FK: log musi przeżyć rekord. Przy ``HARD_DELETE``
wiersz publikacji znika fizycznie, a wpis zostaje jako jedyny ślad, że
istniała. FK z ``CASCADE`` skasowałby dowód razem z rekordem, a FK
z ``PROTECT`` uniemożliwiłby samo kasowanie.
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

__all__ = ["SoftDeleteLog"]


class SoftDeleteLog(models.Model):
    """Wpis audytu pojedynczej operacji soft-delete / restore / hard-delete."""

    class Akcja(models.TextChoices):
        DELETE = "delete", "Usunięcie (kosz)"
        RESTORE = "restore", "Przywrócenie"
        HARD_DELETE = "hard_delete", "Usunięcie trwałe"

    # db_index=False: redundantny wobec Meta.indexes Index(content_type,
    # object_id) — content_type jest tam kolumną wiodącą. Wzorzec jak
    # w OplatyPublikacjiLog.
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name="Typ rekordu",
        db_index=False,
    )
    object_id = models.PositiveIntegerField(db_index=True, verbose_name="ID obiektu")
    content_object = GenericForeignKey("content_type", "object_id")

    akcja = models.CharField(
        max_length=20, choices=Akcja.choices, db_index=True, verbose_name="Akcja"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Użytkownik",
    )
    timestamp = models.DateTimeField(
        auto_now_add=True, db_index=True, verbose_name="Data operacji"
    )
    powod = models.TextField(blank=True, default="", verbose_name="Powód")

    pbn_queue_entry = models.ForeignKey(
        "pbn_export_queue.PBN_Export_Queue",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Wpis kolejki PBN",
    )
    pbn_status = models.CharField(
        max_length=50, blank=True, default="", verbose_name="Status PBN"
    )

    class Meta:
        verbose_name = "Log operacji soft-delete"
        verbose_name_plural = "Logi operacji soft-delete"
        ordering = ["-timestamp"]
        # Bez osobnego Index(["timestamp"]) — pole ma już db_index=True,
        # a drugi identyczny indeks to wyłącznie koszt zapisu przy każdym
        # wpisie logu (a wpis powstaje przy KAŻDYM soft-delete, także dla
        # każdego wiersza *_Autor kasowanego kaskadą).
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.get_akcja_display()}: {self.content_object} ({self.timestamp})"

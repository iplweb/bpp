"""Gotowe wyniki komparatora publikacji PBN.

Porównanie wszystkich prac powiązanych z PBN liczy zadanie w tle
(``tasks.porownaj_publikacje_task``) i zapisuje tutaj; widok tylko czyta.
"""

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models


class RoznicaPublikacjiPBN(models.Model):
    """Jedna praca BPP, której dane różnią się od lokalnej kopii z PBN."""

    TYP_CIAGLE = "ciagle"
    TYP_ZWARTE = "zwarte"
    TYPY = [
        (TYP_CIAGLE, "Wydawnictwo ciągłe"),
        (TYP_ZWARTE, "Wydawnictwo zwarte"),
    ]

    #: Numer przeliczenia; widok czyta wiersze przeliczenia zapisanego
    #: w ``KomparatorPublikacjiMeta.przebieg`` (ostatniego zakończonego).
    przebieg = models.PositiveIntegerField(db_index=True)

    typ = models.CharField(max_length=10, choices=TYPY)
    #: PK pracy w ``Wydawnictwo_Ciagle`` albo ``Wydawnictwo_Zwarte`` (wg typu).
    rekord_id = models.PositiveIntegerField()
    pbn_uid = models.ForeignKey(
        "pbn_api.Publication",
        on_delete=models.CASCADE,
        related_name="+",
    )

    # Kopie pól pracy BPP: filtrowanie, wyszukiwanie i sortowanie bez złączeń
    # z dwiema tabelami wydawnictw.
    rok = models.IntegerField(db_index=True, null=True, blank=True)
    tytul = models.TextField(blank=True, default="")
    doi = models.TextField(blank=True, default="")
    isbn = models.TextField(blank=True, default="")

    #: Klucze pól (``views.COMPARISON_FIELDS``), w których jest różnica.
    pola = ArrayField(models.CharField(max_length=32), default=list)
    #: Lista ``{"key", "field", "bpp_value", "pbn_value"}``.
    roznice = models.JSONField(default=list)

    class Meta:
        verbose_name = "Różnica publikacji BPP-PBN"
        verbose_name_plural = "Różnice publikacji BPP-PBN"
        ordering = ["-rok", "tytul", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["przebieg", "typ", "rekord_id"],
                name="komp_publ_pbn_przebieg_rekord_uniq",
            )
        ]
        indexes = [GinIndex(fields=["pola"], name="komp_publ_pbn_pola_gin")]

    def __str__(self):
        return f"{self.get_typ_display()} #{self.rekord_id}: {self.tytul[:60]}"


class KomparatorPublikacjiMeta(models.Model):
    """Singleton: stan ostatniego przeliczenia komparatora publikacji."""

    STATUS_IDLE = "idle"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_ERROR = "error"

    status = models.CharField(
        "Status",
        max_length=20,
        choices=[
            (STATUS_IDLE, "Bezczynny"),
            (STATUS_RUNNING, "W trakcie"),
            (STATUS_COMPLETED, "Zakończony"),
            (STATUS_ERROR, "Błąd"),
        ],
        default=STATUS_IDLE,
    )
    #: Numer przeliczenia, którego wyniki pokazuje widok (0 = brak wyników).
    przebieg = models.PositiveIntegerField(default=0)
    #: Kiedy zakończono przeliczenie pokazywane w widoku („stan na”).
    ostatnie_uruchomienie = models.DateTimeField(null=True, blank=True)
    rozpoczeto = models.DateTimeField(null=True, blank=True)
    task_id = models.CharField(max_length=64, blank=True, default="")
    liczba_prac = models.PositiveIntegerField(default=0)
    liczba_z_roznicami = models.PositiveIntegerField(default=0)
    ostatni_blad = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Metadane komparatora publikacji"
        verbose_name_plural = "Metadane komparatora publikacji"

    def __str__(self):
        return f"Komparator publikacji PBN (stan na: {self.ostatnie_uruchomienie})"

    @classmethod
    def get_instance(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

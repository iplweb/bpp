from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class RekordWKoszuPominietyPrzezImport(models.Model):
    """Raport: import z PBN trafił na rekord, który u nas jest w koszu.

    DECYZJA WŁAŚCICIELA (listopad 2026): import NIE wskrzesza rekordów
    z kosza. Rekord usunięty w BPP został usunięty świadomie, więc import go
    POMIJA i zgłasza JAWNIE: „w PBN jest rekord X, ale u nas jest usunięty".
    Operator decyduje sam — przywraca rekord z kosza (wtedy kolejny import
    go zaktualizuje) albo zostawia go w koszu.

    Bez pominięcia import albo tworzyłby duplikat (dopasowanie idzie po
    ``Rekord``, który kosza nie widzi), albo wywracał się na unikalnym
    ``pbn_uid`` (rekord w koszu nadal go trzyma).

    Jeden wiersz na (rekord, ścieżka importu) — kolejne importy aktualizują
    datę i licznik, zamiast zalewać raport duplikatami.
    """

    content_type = models.ForeignKey(ContentType, models.CASCADE)
    object_id = models.PositiveIntegerField()
    #: Rekord w koszu. GenericFK, bo import dotyka kilku modeli publikacji.
    rekord = GenericForeignKey("content_type", "object_id")

    pominieto = models.DateTimeField(
        "Ostatnio pominięto",
        auto_now=True,
        db_index=True,
        help_text="Kiedy import ostatnio trafił na ten rekord w koszu.",
    )
    ile_razy = models.PositiveIntegerField(
        "Ile razy", default=1, help_text="Ile razy import pominął ten rekord."
    )
    pbn_uid = models.ForeignKey(
        "pbn_api.Publication",
        models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Publikacja w PBN",
        help_text="Rekord PBN, przez który import trafił na rekord w koszu.",
    )
    zrodlo_importu = models.CharField(
        "Źródło importu",
        max_length=50,
        help_text="Ścieżka importu (articles / books / chapters / …).",
    )
    komunikat = models.TextField("Komunikat")

    class Meta:
        verbose_name = "rekord w koszu pominięty przez import PBN"
        verbose_name_plural = "rekordy w koszu pominięte przez import PBN"
        ordering = ("-pominieto",)
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "zrodlo_importu"],
                name="pbnint_kosz_jeden_wpis_na_rekord",
            ),
        ]

    def __str__(self):
        return self.komunikat

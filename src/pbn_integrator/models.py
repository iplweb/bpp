from django.conf import settings
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


class PobieranieOdpowiednikowPBN(models.Model):
    """Zlecenie grupowego pobrania odpowiedników z PBN (FD#516, FD#519).

    Tworzy je akcja grupowa w adminie („Pobierz odpowiedniki z PBN
    (w tle)”); wykonuje zadanie Celery. To wyłącznie ODCZYT z PBN — nic nie
    jest do PBN wysyłane. ``wyniki`` to raport: jeden wpis na zaznaczony
    rekord, z grupą (ustawiono / nie znaleziono / do ręcznego wyboru…).
    """

    class Rodzaj(models.TextChoices):
        PUBLIKACJE = "publikacje", "Publikacje"
        AUTORZY = "autorzy", "Autorzy"

    zlecil = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.CASCADE,
        verbose_name="Zlecił(a)",
        related_name="+",
    )
    uczelnia = models.ForeignKey(
        "bpp.Uczelnia", models.SET_NULL, null=True, blank=True, related_name="+"
    )
    rodzaj = models.CharField(max_length=16, choices=Rodzaj.choices)
    content_type = models.ForeignKey(
        ContentType, models.CASCADE, verbose_name="Typ rekordów", related_name="+"
    )
    #: Klucze główne zaznaczonych rekordów.
    identyfikatory = models.JSONField(default=list)

    utworzono = models.DateTimeField("Zlecono", auto_now_add=True, db_index=True)
    rozpoczeto = models.DateTimeField("Rozpoczęto", null=True, blank=True)
    zakonczono = models.DateTimeField("Zakończono", null=True, blank=True)
    przetworzono = models.PositiveIntegerField("Przetworzono", default=0)
    #: Ostatni zapis postępu — po nim poznajemy zlecenie przerwane.
    aktywnosc = models.DateTimeField("Ostatnia aktywność", auto_now=True)

    #: Lista słowników: pk, rekord, grupa, opis, pbn_uid.
    wyniki = models.JSONField(default=list)
    blad = models.TextField("Błąd", blank=True, default="")

    class Meta:
        verbose_name = "pobieranie odpowiedników z PBN"
        verbose_name_plural = "pobieranie odpowiedników z PBN"
        ordering = ("-utworzono",)

    def __str__(self):
        return (
            f"Pobieranie odpowiedników z PBN: {self.get_rodzaj_display().lower()}, "
            f"{self.liczba_rekordow} rek. ({self.utworzono:%Y-%m-%d %H:%M})"
        )

    @property
    def liczba_rekordow(self):
        return len(self.identyfikatory)

    @property
    def procent(self):
        if not self.identyfikatory:
            return 100
        return min(100, int(100 * self.przetworzono / len(self.identyfikatory)))

    @property
    def przerwane(self):
        """Niezakończone i bez postępu od dłuższego czasu — np. worker
        został zrestartowany w trakcie. Takie zlecenie można ponowić."""
        from datetime import timedelta

        from django.utils import timezone

        from .pobieranie_odpowiednikow import PRZERWANE_PO_MINUTACH

        if self.zakonczono or self.aktywnosc is None:
            return False
        granica = timezone.now() - timedelta(minutes=PRZERWANE_PO_MINUTACH)
        return self.aktywnosc < granica

    @property
    def stan(self):
        if self.zakonczono:
            return "zakończono z błędem" if self.blad else "zakończono"
        if self.przerwane:
            return "przerwane"
        if self.rozpoczeto:
            return "w toku"
        return "czeka w kolejce"

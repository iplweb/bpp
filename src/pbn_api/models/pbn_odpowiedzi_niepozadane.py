from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import JSONField


class PBNOdpowiedziNiepozadane(models.Model):
    """
    Model przechowujący informacje o niepożądanych odpowiedziach serwera PBN.

    Rejestruje dwa typy zdarzeń:
    1. ZMIANA_UID - gdy PBN zmienia UID publikacji która już miała PBN UID
    2. UID_JUZ_ISTNIEJE - gdy PBN odpowiada UID który już istnieje w bazie
    """

    ZMIANA_UID = "ZMIANA_UID"
    UID_JUZ_ISTNIEJE = "UID_JUZ_ISTNIEJE"

    RODZAJ_ZDARZENIA_CHOICES = [
        (ZMIANA_UID, "Zmiana UID publikacji przez PBN"),
        (UID_JUZ_ISTNIEJE, "PBN odpowiedział UID który już istnieje w bazie"),
    ]

    kiedy_wyslano = models.DateTimeField(
        "Kiedy wysłano", auto_now_add=True, db_index=True
    )

    # GenericForeignKey do publikacji
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, verbose_name="Typ rekordu"
    )
    object_id = models.PositiveIntegerField("ID rekordu", db_index=True)
    rekord = GenericForeignKey("content_type", "object_id")

    dane_wyslane = JSONField("Dane wysłane do PBN", help_text="JSON wysłany do PBN")

    odpowiedz_serwera = JSONField(
        "Odpowiedź serwera PBN", help_text="Odpowiedź z serwera PBN"
    )

    rodzaj_zdarzenia = models.CharField(
        "Rodzaj zdarzenia",
        max_length=50,
        choices=RODZAJ_ZDARZENIA_CHOICES,
        db_index=True,
    )

    uzytkownik = models.CharField(
        "Użytkownik",
        max_length=150,
        blank=True,
        null=True,
        default=None,
        help_text="Login użytkownika który wykonał operację",
    )

    stary_uid = models.CharField(
        "Stary PBN UID",
        max_length=50,
        blank=True,
        default="",
        help_text="Poprzedni PBN UID (dla ZMIANA_UID)",
    )

    nowy_uid = models.CharField(
        "Nowy PBN UID",
        max_length=50,
        help_text="Nowy PBN UID otrzymany z serwera",
        db_index=True,
    )

    class Meta:
        verbose_name = "Niepożądana odpowiedź PBN"
        verbose_name_plural = "Niepożądane odpowiedzi PBN"
        ordering = ["-kiedy_wyslano"]

    def __str__(self):
        return (
            f"{self.get_rodzaj_zdarzenia_display()} - "
            f"{self.nowy_uid} - {self.kiedy_wyslano.strftime('%Y-%m-%d %H:%M:%S')}"
        )

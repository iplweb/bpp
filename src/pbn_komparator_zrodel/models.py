from django.db import models
from django.db.models import CASCADE, SET_NULL


class RozbieznoscZrodlaPBN(models.Model):
    """
    Model przechowujący rozbieżności między danymi źródła w BPP a w PBN.
    Porównuje punkty (Punktacja_Zrodla.punkty_kbn) i dyscypliny (Dyscyplina_Zrodla)
    z danymi z pbn_api.Journal.
    """

    zrodlo = models.ForeignKey(
        "bpp.Zrodlo",
        on_delete=CASCADE,
        related_name="rozbieznosci_pbn",
        verbose_name="Źródło",
    )

    rok = models.PositiveSmallIntegerField(
        "Rok",
        db_index=True,
    )

    # Rozbieżności punktów
    ma_rozbieznosc_punktow = models.BooleanField(
        "Ma rozbieżność punktów",
        default=False,
        db_index=True,
    )
    punkty_bpp = models.DecimalField(
        "Punkty BPP",
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )
    punkty_pbn = models.DecimalField(
        "Punkty PBN",
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )

    # Rozbieżności dyscyplin
    ma_rozbieznosc_dyscyplin = models.BooleanField(
        "Ma rozbieżność dyscyplin",
        default=False,
        db_index=True,
    )
    dyscypliny_bpp = models.TextField(
        "Dyscypliny BPP",
        blank=True,
        default="",
        help_text="Lista kodów dyscyplin w BPP, oddzielona przecinkami",
    )
    dyscypliny_pbn = models.TextField(
        "Dyscypliny PBN",
        blank=True,
        default="",
        help_text="Lista kodów dyscyplin w PBN, oddzielona przecinkami",
    )

    # Metadane
    created_at = models.DateTimeField("Utworzono", auto_now_add=True)
    updated_at = models.DateTimeField("Zaktualizowano", auto_now=True)

    class Meta:
        verbose_name = "Rozbieżność źródła BPP-PBN"
        verbose_name_plural = "Rozbieżności źródeł BPP-PBN"
        unique_together = [["zrodlo", "rok"]]
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["zrodlo"]),
            models.Index(fields=["rok"]),
            models.Index(fields=["ma_rozbieznosc_punktow"]),
            models.Index(fields=["ma_rozbieznosc_dyscyplin"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Rozbieżność: {self.zrodlo.nazwa} ({self.rok})"

    @property
    def ma_jakiekolwiek_rozbieznosci(self):
        return self.ma_rozbieznosc_punktow or self.ma_rozbieznosc_dyscyplin


class KomparatorZrodelMeta(models.Model):
    """
    Singleton model przechowujący metadane o ostatnim uruchomieniu komparatora.
    """

    ostatnie_uruchomienie = models.DateTimeField(
        "Ostatnie uruchomienie",
        null=True,
        blank=True,
    )
    status = models.CharField(
        "Status",
        max_length=20,
        choices=[
            ("idle", "Bezczynny"),
            ("running", "W trakcie"),
            ("completed", "Zakończony"),
            ("error", "Błąd"),
        ],
        default="idle",
    )
    ostatni_blad = models.TextField(
        "Ostatni błąd",
        blank=True,
        default="",
    )
    statystyki = models.JSONField(
        "Statystyki",
        default=dict,
        blank=True,
    )

    class Meta:
        verbose_name = "Metadane komparatora źródeł"
        verbose_name_plural = "Metadane komparatora źródeł"

    def __str__(self):
        return f"Metadane komparatora (ostatnie uruchomienie: {self.ostatnie_uruchomienie})"

    @classmethod
    def get_instance(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class LogAktualizacjiZrodla(models.Model):
    """Log zmian wprowadzonych przez komparator."""

    zrodlo = models.ForeignKey(
        "bpp.Zrodlo",
        on_delete=SET_NULL,
        null=True,
        related_name="logi_aktualizacji_pbn",
        verbose_name="Źródło",
    )
    rok = models.PositiveSmallIntegerField("Rok")
    typ_zmiany = models.CharField(
        "Typ zmiany",
        max_length=20,
        choices=[
            ("punkty", "Punkty"),
            ("dyscypliny", "Dyscypliny"),
            ("oba", "Punkty i dyscypliny"),
        ],
    )
    wartosc_przed = models.TextField("Wartość przed", blank=True, default="")
    wartosc_po = models.TextField("Wartość po", blank=True, default="")
    user = models.ForeignKey(
        "bpp.BppUser",
        on_delete=SET_NULL,
        null=True,
        blank=True,
        verbose_name="Użytkownik",
    )
    created_at = models.DateTimeField("Kiedy", auto_now_add=True)

    class Meta:
        verbose_name = "Log aktualizacji źródła"
        verbose_name_plural = "Logi aktualizacji źródeł"
        ordering = ["-created_at"]

    def __str__(self):
        zrodlo_nazwa = self.zrodlo.nazwa if self.zrodlo else "(usunięte)"
        return f"Aktualizacja {zrodlo_nazwa} ({self.rok}): {self.typ_zmiany}"


class BrakujacaDyscyplinaPBN(models.Model):
    """
    Dyscyplina występująca w danych PBN, która nie istnieje w bazie BPP.
    Dane są aktualizowane po każdym pobraniu źródeł z PBN (download_journals task).
    """

    kod_pbn = models.CharField(
        "Kod PBN",
        max_length=10,
        unique=True,
        help_text="Kod dyscypliny w formacie PBN, np. '503'",
    )
    kod_bpp = models.CharField(
        "Kod BPP",
        max_length=10,
        help_text="Kod dyscypliny przekonwertowany do formatu BPP, np. '5.3'",
    )
    nazwa = models.CharField(
        "Nazwa",
        max_length=255,
        blank=True,
        default="",
    )
    liczba_zrodel = models.PositiveIntegerField(
        "Liczba źródeł",
        default=0,
        help_text="Ile źródeł w PBN używa tej dyscypliny",
    )
    ostatnia_aktualizacja = models.DateTimeField(
        "Ostatnia aktualizacja",
        auto_now=True,
    )

    class Meta:
        verbose_name = "Brakująca dyscyplina PBN"
        verbose_name_plural = "Brakujące dyscypliny PBN"
        ordering = ["kod_pbn"]

    def __str__(self):
        return f"{self.kod_pbn} ({self.kod_bpp}): {self.nazwa}"

from django.db import models

from rozbieznosci.metryki import METRYKA_CHOICES


class IgnorowanaRozbieznosc(models.Model):
    metryka = models.CharField("Metryka", max_length=16, choices=METRYKA_CHOICES)
    rekord = models.ForeignKey(
        "bpp.Wydawnictwo_Ciagle",
        on_delete=models.CASCADE,
        verbose_name="Rekord",
    )
    created_on = models.DateTimeField("Utworzono", auto_now_add=True)

    class Meta:
        unique_together = [("metryka", "rekord")]
        verbose_name = "ignorowana rozbieżność"
        verbose_name_plural = "ignorowane rozbieżności"

    def __str__(self):
        return f"Ignoruj rozbieżność {self.metryka} dla rekordu {self.rekord_id}"


class RozbieznoscLog(models.Model):
    metryka = models.CharField("Metryka", max_length=16, choices=METRYKA_CHOICES)
    rekord = models.ForeignKey(
        "bpp.Wydawnictwo_Ciagle",
        on_delete=models.CASCADE,
        verbose_name="Rekord",
    )
    zrodlo = models.ForeignKey(
        "bpp.Zrodlo",
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Źródło",
    )
    wartosc_przed = models.DecimalField(
        "Wartość przed zmianą", max_digits=10, decimal_places=3, null=True
    )
    wartosc_po = models.DecimalField(
        "Wartość po zmianie", max_digits=10, decimal_places=3, null=True
    )
    user = models.ForeignKey(
        "bpp.BppUser",
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Użytkownik",
    )
    created_on = models.DateTimeField("Kiedy", auto_now_add=True)

    class Meta:
        ordering = ["-created_on"]
        verbose_name = "log zmiany punktacji"
        verbose_name_plural = "logi zmian punktacji"

    def __str__(self):
        return (
            f"Zmiana {self.metryka}: rekord {self.rekord_id} "
            f"({self.wartosc_przed} -> {self.wartosc_po})"
        )

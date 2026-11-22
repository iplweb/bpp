from django.db import models

__all__ = ["Wersja_Przeliczenia"]


class Wersja_Przeliczenia(models.Model):
    """Wersja przeliczenia, które BPP ostatnio zlecił na tej bazie.

    Jeden wiersz na przeliczenie z rejestru ``bpp.przeliczenia.PRZELICZENIA``.
    Gdy wersja w kodzie jest wyższa niż tu zapisana, worker Celery po starcie
    zleca przeliczenie w tle i zapisuje nową wersję (patrz
    ``bpp.przeliczenia.zlec_zalegle_przeliczenia``).
    """

    nazwa = models.CharField(max_length=100, unique=True)
    wersja = models.PositiveIntegerField(default=0)
    zlecono = models.DateTimeField(null=True, blank=True)
    oznaczono_rekordow = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "wersja przeliczenia"
        verbose_name_plural = "wersje przeliczeń"

    def __str__(self):
        return f"{self.nazwa}: wersja {self.wersja}"

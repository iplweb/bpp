from django.db import models


class RodzajJednostki(models.Model):
    """Słownik rodzajów jednostki organizacyjnej (per-tenant edytowalny).

    Zastępuje dawny CharField Jednostka.rodzaj_jednostki. Behawior wyłącznie
    we flagach, nie w nazwie — 'Wydział' to zwykła etykieta.
    """

    nazwa = models.CharField(max_length=200, unique=True)
    skrot = models.CharField(max_length=50, blank=True, default="")
    kolejnosc = models.PositiveIntegerField(default=0)
    wyklucz_z_rankingu_autorow = models.BooleanField(default=False)
    pokazuj_jako_odrebna_sekcje = models.BooleanField(default=False)
    pokazuj_strukture_podjednostek = models.BooleanField(
        "Pokazuj stronę w stylu wydziału", default=False
    )

    class Meta:
        verbose_name = "rodzaj jednostki"
        verbose_name_plural = "rodzaje jednostek"
        ordering = ["kolejnosc", "nazwa"]
        app_label = "bpp"

    def __str__(self):
        return self.nazwa

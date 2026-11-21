from bpp.models.abstract import ModelZNazwa
from bpp.models.soft_delete import BppSoftDeleteSlownikMixin


class Seria_Wydawnicza(BppSoftDeleteSlownikMixin, ModelZNazwa):
    """Seria wydawnicza. Kosz: tylko seria bez publikacji (także w koszu)."""

    class Meta:
        verbose_name_plural = "serie wydawnicze"
        verbose_name = "seria wydawnicza"
        ordering = ("nazwa",)

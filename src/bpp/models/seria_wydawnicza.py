from bpp.models.abstract import ModelZNazwa
from bpp.models.soft_delete import BppSoftDeleteSlownikMixin


class Seria_Wydawnicza(BppSoftDeleteSlownikMixin, ModelZNazwa):
    """Seria wydawnicza. Kosz: tylko seria bez publikacji (także w koszu)."""

    pola_unikalne_kosza = ("nazwa",)

    class Meta:
        verbose_name_plural = "serie wydawnicze"
        verbose_name = "seria wydawnicza"
        ordering = ("nazwa",)

    def relacje_chronione_kosza(self):
        from bpp.models import Wydawnictwo_Zwarte

        return [(Wydawnictwo_Zwarte, "seria_wydawnicza")]

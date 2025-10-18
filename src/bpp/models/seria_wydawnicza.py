from bpp.models.abstract import ModelZNazwa


class Seria_Wydawnicza(ModelZNazwa):
    class Meta:
        verbose_name_plural = "serie wydawnicze"
        verbose_name = "seria wydawnicza"
        ordering = ("nazwa",)

    pass

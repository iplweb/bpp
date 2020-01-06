# -*- encoding: utf-8 -*-
from bpp.models.abstract import ModelZNazwa, ModelZISSN


class Seria_Wydawnicza(ModelZNazwa):
    class Meta:
        verbose_name_plural = "serie wydawnicze"
        verbose_name = "seria wydawnicza"
        ordering = ('nazwa',)
    pass

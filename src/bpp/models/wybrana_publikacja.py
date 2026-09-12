"""Wybrane (wyróżnione) publikacje autora — ręcznie wskazane prace.

Publikacje w BPP są polimorficzne (Wydawnictwo_Zwarte / Wydawnictwo_Ciagle /
Patent / Praca_*), więc wskazujemy je przez GenericForeignKey
(``content_type`` + ``object_id``) — tak samo jak identyfikuje je cache
``Rekord``.
"""

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import CASCADE

from bpp.models.autor import Autor

__all__ = ["WybranaPublikacjaAutora"]


class WybranaPublikacjaAutora(models.Model):
    autor = models.ForeignKey(Autor, CASCADE, related_name="wybrane_publikacje")
    content_type = models.ForeignKey(ContentType, CASCADE)
    object_id = models.PositiveIntegerField()
    publikacja = GenericForeignKey("content_type", "object_id")
    kolejnosc = models.PositiveIntegerField("Kolejność", default=0)

    class Meta:
        app_label = "bpp"
        verbose_name = "wybrana publikacja autora"
        verbose_name_plural = "wybrane publikacje autora"
        ordering = ("autor", "kolejnosc")
        unique_together = [("autor", "content_type", "object_id")]

    def __str__(self):
        return f"{self.autor}: {self.publikacja}"

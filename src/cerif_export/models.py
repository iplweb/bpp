from django.contrib.contenttypes.models import ContentType
from django.db import models


class OdpietaPrzynaleznosc(models.Model):
    """Publikacja WYPADŁA z setu uczelni, bo odpięto jej ostatniego autora.

    Przynależność wydawnictwa/patentu do uczelni wynika z wierszy ``*_Autor``
    (autor afiliowany w jednostce uczelni). Te wiersze nie mają kosza —
    odpięcie autora to twarde ``DELETE``, więc po odpięciu OSTATNIEGO autora
    uczelni rekord nie należałby do jej nadzbioru (``przynaleznosc``)
    i harvester OAI-PMH/CERIF nie dostałby nagrobka. Ten wiersz trzyma
    rekord w nadzbiorze; że nie jest widoczny, rozstrzyga ``queryset`` —
    różnica daje nagrobek.

    Zakłada go / usuwa ``cerif_export.signals`` (post_delete / post_save
    wierszy ``*_Autor``). Gdy autor uczelni wróci, wiersz znika — rekord
    jest znów w secie zwykłą drogą.
    """

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    uczelnia = models.ForeignKey("bpp.Uczelnia", on_delete=models.CASCADE)
    utworzono = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "odpięta przynależność do uczelni"
        verbose_name_plural = "odpięte przynależności do uczelni"
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "uczelnia"],
                name="cerif_odpieta_przynaleznosc_unikalna",
            )
        ]

    def __str__(self):
        return f"{self.content_type_id}/{self.object_id} @ {self.uczelnia_id}"

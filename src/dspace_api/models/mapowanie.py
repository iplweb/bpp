from django.db import models


class Mapowanie_DSpace(models.Model):
    """Mapuje (Uczelnia, Charakter_Formalny) na kolekcję DSpace."""

    uczelnia = models.ForeignKey(
        "bpp.Uczelnia", on_delete=models.CASCADE, verbose_name="Uczelnia"
    )
    charakter_formalny = models.ForeignKey(
        "bpp.Charakter_Formalny",
        on_delete=models.CASCADE,
        verbose_name="Charakter formalny",
    )
    collection_uuid = models.UUIDField("UUID kolekcji DSpace")
    opis = models.CharField("Opis", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "Mapowanie DSpace"
        verbose_name_plural = "Mapowania DSpace"
        unique_together = (("uczelnia", "charakter_formalny"),)

    def __str__(self):
        return f"{self.uczelnia} / {self.charakter_formalny} → {self.collection_uuid}"

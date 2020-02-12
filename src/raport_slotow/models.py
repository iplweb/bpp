from django.db import models
from django.db.models.deletion import DO_NOTHING

from bpp.fields import YearField


class RaportZerowyEntry(models.Model):
    autor = models.ForeignKey("bpp.Autor", DO_NOTHING, primary_key=True)
    rok = YearField()
    dyscyplina_naukowa = models.ForeignKey("bpp.Dyscyplina_Naukowa", DO_NOTHING)

    class Meta:
        managed = False
        ordering = (
            "autor",
            "rok",
        )

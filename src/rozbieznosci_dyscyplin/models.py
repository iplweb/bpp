from django.db import models
from django.db.models import DO_NOTHING

from bpp.fields import YearField
from bpp.models import TupleField


class RozbieznosciViewBase(models.Model):
    id = TupleField(models.IntegerField(), size=3, primary_key=True)
    rekord = models.ForeignKey("bpp.Rekord", DO_NOTHING, related_name="+")
    rok = YearField()
    autor = models.ForeignKey("bpp.Autor", DO_NOTHING, related_name="+")
    dyscyplina_rekordu = models.ForeignKey("bpp.Dyscyplina_Naukowa", DO_NOTHING, related_name="+", null=True,
                                           blank=True)
    dyscyplina_autora = models.ForeignKey("bpp.Dyscyplina_Naukowa", DO_NOTHING, related_name="+")
    subdyscyplina_autora = models.ForeignKey("bpp.Dyscyplina_Naukowa", DO_NOTHING, related_name="+", null=True,
                                             blank=True)

    class Meta:
        managed = False
        abstract = True


class BrakPrzypisaniaView(RozbieznosciViewBase):
    class Meta:
        managed = False


class RozbieznePrzypisaniaView(RozbieznosciViewBase):
    class Meta:
        managed = False


class RozbieznosciView(RozbieznosciViewBase):
    class Meta:
        managed = False

from django.db import models
from django.db.models import DO_NOTHING

from bpp.fields import YearField
from bpp.models import BazaModeluOdpowiedzialnosciAutorow, TupleField


class RozbieznosciViewBase(models.Model):
    id = TupleField(models.IntegerField(), size=3, primary_key=True)
    rekord = models.ForeignKey("bpp.Rekord", DO_NOTHING, related_name="+")
    rok = YearField()
    autor = models.ForeignKey("bpp.Autor", DO_NOTHING, related_name="+")
    dyscyplina_rekordu = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa", DO_NOTHING, related_name="+", null=True, blank=True
    )
    dyscyplina_autora = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa", DO_NOTHING, related_name="+"
    )
    subdyscyplina_autora = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa", DO_NOTHING, related_name="+", null=True, blank=True
    )

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
    # Uwaga: w sytuacji, gdy praca będzie miała jednego i tego samego autora (np w roli redaoktora
    # oraz autora) to ten model i funkcja get_wydawnictwo_autor_obj zawiedzie.
    class Meta:
        managed = False
        verbose_name = "rozbieżność rekordu i dyscyplin"
        verbose_name_plural = "rozbieżności rekordów i dyscyplin"

    def get_wydawnictwo_autor_obj(self) -> BazaModeluOdpowiedzialnosciAutorow:
        # Uwaga: w sytuacji, gdy praca będzie miała jednego i tego samego autora (np w roli redaoktora
        # oraz autora) to ten model i funkcja get_wydawnictwo_autor_obj zawiedzie (zwraca wyłacznie pierwszy
        # rekord z powiazaniem autora + rekordu)
        return self.rekord.original.autorzy_set.filter(autor=self.autor).first()


class RozbieznosciZrodelView(models.Model):
    class Meta:
        managed = False
        verbose_name = "rozbieżność dyscyplin źródeł"
        verbose_name_plural = "rozbieżności dyscyplin źródeł"

    id = TupleField(models.IntegerField(), size=4, primary_key=True)
    zrodlo = models.ForeignKey("bpp.Zrodlo", on_delete=DO_NOTHING, related_name="+")
    wydawnictwo_ciagle = models.ForeignKey(
        "bpp.Wydawnictwo_Ciagle", on_delete=DO_NOTHING, related_name="+"
    )
    autor = models.ForeignKey("bpp.Autor", on_delete=DO_NOTHING, related_name="+")
    dyscyplina_naukowa = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa", on_delete=DO_NOTHING, related_name="+"
    )

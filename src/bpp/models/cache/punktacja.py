# Cache'ujemy:
# - Wydawnictwo_Zwarte
# - Wydawnictwo_Ciagle
# - Patent
# - Praca_Doktorska
# - Praca_Habilitacyjna

from django.db import models
from django.db.models import ForeignKey
from django.db.models.deletion import DO_NOTHING

from django.contrib.postgres.fields.array import ArrayField

from bpp.models.autor import Autor
from bpp.models.dyscyplina_naukowa import Autor_Dyscyplina, Dyscyplina_Naukowa
from bpp.models.fields import TupleField


class Cache_Punktacja_Dyscypliny(models.Model):
    rekord_id = TupleField(models.IntegerField(), size=2, db_index=True)
    # rekord = ForeignKey('bpp.Rekord', models.CASCADE)
    dyscyplina = ForeignKey(Dyscyplina_Naukowa, models.CASCADE)
    pkd = models.DecimalField(max_digits=20, decimal_places=4)
    slot = models.DecimalField(max_digits=20, decimal_places=4)

    autorzy_z_dyscypliny = ArrayField(
        models.PositiveIntegerField(), blank=True, null=True
    )
    zapisani_autorzy_z_dyscypliny = ArrayField(
        models.TextField(), blank=True, null=True
    )

    class Meta:
        ordering = ("dyscyplina__nazwa",)

    def serialize(self):
        return [self.rekord_id, self.dyscyplina_id, str(self.pkd), str(self.slot)]


class Cache_Punktacja_Autora_Base(models.Model):
    autor = ForeignKey(Autor, models.CASCADE)
    jednostka = ForeignKey("bpp.Jednostka", models.CASCADE)
    dyscyplina = ForeignKey(Dyscyplina_Naukowa, models.CASCADE)
    pkdaut = models.DecimalField(max_digits=20, decimal_places=4)
    slot = models.DecimalField(max_digits=20, decimal_places=4)

    class Meta:
        ordering = ("autor__nazwisko", "dyscyplina__nazwa")
        abstract = True


class Cache_Punktacja_Autora(Cache_Punktacja_Autora_Base):
    rekord_id = TupleField(models.IntegerField(), size=2, db_index=True)

    class Meta:
        ordering = ("autor__nazwisko", "dyscyplina__nazwa")

    def serialize(self):
        return [
            self.rekord_id,
            self.autor_id,
            self.jednostka_id,
            self.dyscyplina_id,
            str(self.pkdaut),
            str(self.slot),
        ]

    def dyscyplina_pracy(self):
        return self.dyscyplina

    def dyscypliny_autora(self):
        from .rekord import Rekord

        return Autor_Dyscyplina.objects.get(
            rok=Rekord.objects.get(pk=self.rekord_id).rok,
            autor_id=self.autor_id,
        )

    def czy_autor_ma_alternatywna_dyscypline(self):
        # Zwraca True jeżeli autor ma drugą dyscyplinę za ten rok, inną niż obecnie wybrana;
        # używane do wydruków oświadczeń
        try:
            ad = self.dyscypliny_autora()
        except Autor_Dyscyplina.DoesNotExist:
            return False

        if ad.dwie_dyscypliny():
            return True


class Cache_Punktacja_Autora_Query(Cache_Punktacja_Autora_Base):
    rekord = ForeignKey("bpp.Rekord", DO_NOTHING)

    class Meta:
        db_table = "bpp_cache_punktacja_autora"
        managed = False


class Cache_Punktacja_Autora_Query_View(models.Model):
    """W porównaniu do Cache_Punktacja_Autora, mam jeszcze listę zapisanych
    autorów z dyscypliny. A skąd? A z widoku bazodanowego, który bierze
    też pod uwagę Cache_Punktacja_Dyscypliny.
    """

    rekord = ForeignKey("bpp.Rekord", DO_NOTHING)
    autor = ForeignKey(Autor, DO_NOTHING)
    jednostka = ForeignKey("bpp.Jednostka", DO_NOTHING)
    dyscyplina = ForeignKey(Dyscyplina_Naukowa, DO_NOTHING)
    pkdaut = models.DecimalField(max_digits=20, decimal_places=4)
    slot = models.DecimalField(max_digits=20, decimal_places=4)
    zapisani_autorzy_z_dyscypliny = ArrayField(models.TextField())

    class Meta:
        ordering = ("rekord__tytul_oryginalny", "dyscyplina__nazwa")
        db_table = "bpp_cache_punktacja_autora_view"
        managed = False


class Cache_Punktacja_Autora_Sum(Cache_Punktacja_Autora_Base):
    rekord = ForeignKey("bpp.Rekord", DO_NOTHING)
    autor = ForeignKey(Autor, DO_NOTHING)
    jednostka = ForeignKey("bpp.Jednostka", DO_NOTHING)
    dyscyplina = ForeignKey(Dyscyplina_Naukowa, DO_NOTHING)
    pkdautslot = models.FloatField()
    pkdautsum = models.FloatField()
    pkdautslotsum = models.FloatField()

    class Meta:
        db_table = "bpp_temporary_cpaq"
        managed = False
        ordering = (
            "autor",
            "dyscyplina",
            "-pkdautslot",
        )


class Cache_Punktacja_Autora_Sum_Ponizej(Cache_Punktacja_Autora_Base):
    rekord = ForeignKey("bpp.Rekord", DO_NOTHING)
    autor = ForeignKey(Autor, DO_NOTHING)
    jednostka = ForeignKey("bpp.Jednostka", DO_NOTHING)
    dyscyplina = ForeignKey(Dyscyplina_Naukowa, DO_NOTHING)
    pkdautslot = models.FloatField()
    pkdautsum = models.FloatField()
    pkdautslotsum = models.FloatField()

    class Meta:
        db_table = "bpp_temporary_cpaq_2"
        managed = False
        ordering = (
            "autor",
            "dyscyplina",
            "pkdautslot",
        )


class Cache_Punktacja_Autora_Sum_Group_Ponizej(models.Model):
    autor = models.OneToOneField(Autor, DO_NOTHING, primary_key=True)
    jednostka = ForeignKey("bpp.Jednostka", DO_NOTHING)
    dyscyplina = ForeignKey(Dyscyplina_Naukowa, DO_NOTHING)
    pkdautsum = models.FloatField()
    pkdautslotsum = models.FloatField()

    class Meta:
        db_table = "bpp_temporary_cpasg_2"
        managed = False
        ordering = (
            "autor",
            "dyscyplina",
        )


class Cache_Punktacja_Autora_Sum_Gruop(models.Model):
    autor = models.OneToOneField(Autor, DO_NOTHING, primary_key=True)
    jednostka = ForeignKey("bpp.Jednostka", DO_NOTHING)
    dyscyplina = ForeignKey(Dyscyplina_Naukowa, DO_NOTHING)
    pkdautsum = models.FloatField()
    pkdautslotsum = models.FloatField()

    class Meta:
        db_table = "bpp_temporary_cpasg"
        managed = False
        ordering = (
            "autor",
            "dyscyplina",
        )

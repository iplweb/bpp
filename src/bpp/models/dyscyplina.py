from django.db import models
from django.db.models import PositiveSmallIntegerField
from mptt.models import MPTTModel, TreeForeignKey


class Dyscyplina_Naukowa(MPTTModel):
    nazwa = models.CharField(max_length=200)
    dyscyplina_nadrzedna = TreeForeignKey(
        'self',
        null=True,
        blank=True,
        related_name='subdyscypliny',
        db_index=True)

    class MPTTMeta:
        order_insertion_by = ['nazwa']


class Autor_Dyscyplina(models.Model):
    rok = PositiveSmallIntegerField()
    autor = models.ForeignKey("bpp.Autor")
    dyscyplina = models.ForeignKey("bpp.Dyscyplina_Naukowa")

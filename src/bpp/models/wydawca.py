from django.db import models
from django.db.models import CASCADE

from bpp.fields import YearField
from bpp.models import ModelZNazwa


class Wydawca(ModelZNazwa):
    class Meta:
        verbose_name_plural = 'wydawcy'
        verbose_name = 'wydawca'
        ordering = ('nazwa',)

    def get_tier(self, rok):
        ret = self.poziom_wydawcy_set.filter(rok=rok).first()
        if ret is None:
            return -1
        return ret.poziom


class Poziom_Wydawcy(models.Model):
    rok = YearField(db_index=True)
    wydawca = models.ForeignKey(Wydawca, CASCADE)
    poziom = models.PositiveSmallIntegerField(
        choices=[(None, "nieokreślono"),
                 (1, "poziom I"),
                 (2, "poziom II")
                 ],
        blank=True, null=True
    )

    class Meta:
        unique_together = ('rok', 'wydawca')
        verbose_name = 'poziom wydawcy'
        verbose_name_plural = 'poziomy wydawcy'
        ordering = ('rok',)

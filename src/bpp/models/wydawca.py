from django.db import models
from django.core.exceptions import ValidationError

from bpp.fields import YearField
from bpp.models import ModelZNazwa


class Wydawca(ModelZNazwa):
    alias_dla = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True
    )

    class Meta:
        verbose_name_plural = "wydawcy"
        verbose_name = "wydawca"
        ordering = ("nazwa",)

    def clean(self):
        if self.pk:
            if hasattr(self, "alias_dla_id") and self.pk == self.alias_dla_id:
                raise ValidationError("Rekord nie może być aliasem sam dla siebie")

            if hasattr(self, "alias_dla_id"):
                if self.poziom_wydawcy_set.count():
                    raise ValidationError(
                        "Wydawca ma przypisane poziomy wydawcy, "
                        "stąd nie można zmienić go w alias. "
                    )

    def save(self, *args, **kw):
        self.clean()
        return super().save(*args, **kw)

    def get_tier(self, rok):
        if self.alias_dla is not None:
            return self.alias_dla.get_tier(rok)

        ret = self.poziom_wydawcy_set.filter(rok=rok).first()
        if ret is None:
            return -1
        return ret.poziom


class Poziom_Wydawcy(models.Model):
    rok = YearField(db_index=True)
    wydawca = models.ForeignKey(Wydawca, models.CASCADE)
    poziom = models.PositiveSmallIntegerField(
        choices=[(None, "nieokreślono"), (1, "poziom I"), (2, "poziom II")],
        blank=True,
        null=True,
    )

    class Meta:
        unique_together = ("rok", "wydawca")
        verbose_name = "poziom wydawcy"
        verbose_name_plural = "poziomy wydawcy"
        ordering = ("rok",)

    def clean(self):
        if hasattr(self, "wydawca_id") and self.wydawca_id:
            if self.wydawca.alias_dla is not None:
                raise ValidationError(
                    "Nie można przypisywać poziomu wydawcy dla aliasów."
                )

    def save(self, *args, **kw):
        self.clean()
        return super().save(*args, **kw)

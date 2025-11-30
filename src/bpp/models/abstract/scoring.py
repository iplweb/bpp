"""
Modele abstrakcyjne związane z punktacją.
"""

from decimal import Decimal

from django.db import models

from bpp import const

from .utils import ImpactFactorField


class ModelPunktowanyBaza(models.Model):
    impact_factor = ImpactFactorField(
        db_index=True,
    )
    punkty_kbn = models.DecimalField(
        "punkty MNiSW/MEiN",
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
        db_index=True,
    )
    index_copernicus = models.DecimalField(
        "Index Copernicus",
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
        db_index=True,
    )
    punktacja_wewnetrzna = models.DecimalField(
        "Punktacja wewnętrzna",
        max_digits=6,
        decimal_places=2,
        default=Decimal("0.00"),
        db_index=True,
    )
    punktacja_snip = models.DecimalField(
        "Punktacja SNIP",
        max_digits=6,
        decimal_places=3,
        default=Decimal("0.000"),
        db_index=True,
        help_text="""CiteScore SNIP (Source Normalized Impact per Paper)""",
    )

    class Meta:
        abstract = True


class ModelZKwartylami(models.Model):
    kwartyl_w_scopus = models.IntegerField(
        "Kwartyl w SCOPUS",
        choices=const.KWARTYLE,
        default=None,
        blank=True,
        null=True,
    )

    kwartyl_w_wos = models.IntegerField(
        "Kwartyl w WoS", choices=const.KWARTYLE, default=None, blank=True, null=True
    )

    class Meta:
        abstract = True


class ModelPunktowany(ModelPunktowanyBaza):
    """Model zawiereający informację o punktacji."""

    weryfikacja_punktacji = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def ma_punktacje(self):
        """Zwraca 'True', jeżeli ten rekord ma jakąkolwiek punktację,
        czyli jeżeli dowolne z jego pól ma wartość nie-zerową"""

        for pole in POLA_PUNKTACJI:
            f = getattr(self, pole)

            if f is None:
                continue

            if isinstance(f, Decimal):
                if not f.is_zero():
                    return True
            else:
                if f != 0:
                    return True

        return False


# Compute POLA_PUNKTACJI after models are defined
POLA_PUNKTACJI = [
    x.name for x in ModelPunktowany._meta.fields if x.name != "weryfikacja_punktacji"
] + [x.name for x in ModelZKwartylami._meta.fields]

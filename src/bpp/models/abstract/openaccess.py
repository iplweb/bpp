"""
Modele abstrakcyjne związane z Open Access.
"""

from django.db import models
from django.db.models import CASCADE


class ModelZOpenAccess(models.Model):
    openaccess_wersja_tekstu = models.ForeignKey(
        "Wersja_Tekstu_OpenAccess",
        CASCADE,
        verbose_name="OpenAccess: wersja tekstu",
        blank=True,
        null=True,
    )

    openaccess_licencja = models.ForeignKey(
        "Licencja_OpenAccess",
        CASCADE,
        verbose_name="OpenAccess: licencja",
        blank=True,
        null=True,
    )

    openaccess_czas_publikacji = models.ForeignKey(
        "Czas_Udostepnienia_OpenAccess",
        CASCADE,
        verbose_name="OpenAccess: czas udostępnienia",
        blank=True,
        null=True,
    )

    openaccess_ilosc_miesiecy = models.PositiveIntegerField(
        "OpenAccess: ilość miesięcy",
        blank=True,
        null=True,
        help_text="Ilość miesięcy jakie upłynęły od momentu opublikowania do momentu udostępnienia",
    )

    openaccess_data_opublikowania = models.DateField(
        "OpenAccess: data publikacji",
        blank=True,
        null=True,
    )

    class Meta:
        abstract = True


class ModelZLiczbaCytowan(models.Model):
    liczba_cytowan = models.PositiveIntegerField(
        verbose_name="Liczba cytowań",
        null=True,
        blank=True,
        help_text="""Wartość aktualizowana jest automatycznie raz na kilka dni w przypadku
        skonfigurowania dostępu do API WOS AMR (przez obiekt 'Uczelnia'). Możesz również
        czaktualizować tą wartość ręcznie, naciskając przycisk. """,
    )

    class Meta:
        abstract = True

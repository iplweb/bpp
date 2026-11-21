"""
Modele abstrakcyjne związane z Open Access.
"""

import datetime

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import PROTECT

#: Najwcześniejszy dopuszczalny rok udostępnienia w otwartym dostępie.
OPENACCESS_ROK_MIN = 1900

#: O ile lat w przód od bieżącego roku może sięgać rok udostępnienia
#: (embargo „po opublikowaniu” bywa wieloletnie, ale nie dłuższe).
OPENACCESS_ROK_MAX_W_PRZOD = 10


class ModelZOpenAccess(models.Model):
    openaccess_wersja_tekstu = models.ForeignKey(
        "Wersja_Tekstu_OpenAccess",
        PROTECT,
        verbose_name="OpenAccess: wersja tekstu",
        blank=True,
        null=True,
    )

    openaccess_licencja = models.ForeignKey(
        "Licencja_OpenAccess",
        PROTECT,
        verbose_name="OpenAccess: licencja",
        blank=True,
        null=True,
    )

    openaccess_czas_publikacji = models.ForeignKey(
        "Czas_Udostepnienia_OpenAccess",
        PROTECT,
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


class ModelZOpenAccessRokUdostepnienia(models.Model):
    """Sam rok udostępnienia w otwartym dostępie (Freshdesk #281).

    Alternatywa dla ``openaccess_data_opublikowania``, gdy redakcja zna
    tylko rok udostępnienia. Do PBN wysyłany jako ``releaseDateYear``.

    Celowo NIE w ``ModelZOpenAccess``: z tamtej klasy dziedziczy też
    ``Rekord`` (zmaterializowany widok ``bpp_rekord_mat``), więc nowe pole
    wymagałoby przebudowy widoku. Pole jest potrzebne tylko w wydawnictwach
    ciągłych i zwartych (formularz, eksport do PBN, import z PBN).
    """

    openaccess_rok_udostepnienia = models.PositiveSmallIntegerField(
        "OpenAccess: rok udostępnienia",
        blank=True,
        null=True,
        validators=[MinValueValidator(OPENACCESS_ROK_MIN)],
        help_text="Sam rok udostępnienia pracy w otwartym dostępie — wypełnij "
        "zamiast daty udostępnienia, gdy znasz tylko rok. Wysyłany do PBN "
        "jako rok udostępnienia (bez miesiąca i dnia).",
    )

    class Meta:
        abstract = True

    def clean(self):
        rok = self.openaccess_rok_udostepnienia
        if rok is None:
            return

        if getattr(self, "openaccess_data_opublikowania", None) is not None:
            komunikat = (
                "Podaj albo datę udostępnienia w otwartym dostępie, albo sam "
                "rok udostępnienia — nie oba naraz. Wyczyść jedno z tych pól."
            )
            raise ValidationError(
                {
                    "openaccess_data_opublikowania": komunikat,
                    "openaccess_rok_udostepnienia": komunikat,
                }
            )

        # Zakres sprawdzany także tutaj, nie tylko walidatorem pola: część
        # modeli publikacji nadpisuje ``clean_fields`` bez wołania ``super()``.
        rok_max = datetime.date.today().year + OPENACCESS_ROK_MAX_W_PRZOD
        if not OPENACCESS_ROK_MIN <= rok <= rok_max:
            raise ValidationError(
                {
                    "openaccess_rok_udostepnienia": (
                        f"Rok udostępnienia {rok} jest spoza dopuszczalnego "
                        f"zakresu {OPENACCESS_ROK_MIN}–{rok_max}."
                    )
                }
            )


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

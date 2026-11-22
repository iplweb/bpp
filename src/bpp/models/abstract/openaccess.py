"""
Modele abstrakcyjne związane z Open Access.
"""

import datetime

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
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


class ModelZOpenAccessMiesiacIRokUdostepnienia(models.Model):
    """Miesiąc i rok udostępnienia w otwartym dostępie (Freshdesk #281).

    Alternatywa dla pełnej daty ``openaccess_data_opublikowania``, gdy
    redakcja zna tylko miesiąc i rok udostępnienia. Do PBN wysyłane jako
    ``releaseDateMonth`` + ``releaseDateYear``. Sam rok NIE wystarcza: PBN
    odrzuca go walidacją „pełna data albo miesiąc i rok jest wymagana”
    (sprawdzone na produkcyjnym PBN, FD#281).

    Celowo NIE w ``ModelZOpenAccess``: z tamtej klasy dziedziczy też
    ``Rekord`` (zmaterializowany widok ``bpp_rekord_mat``), więc nowe pola
    wymagałyby przebudowy widoku. Pola są potrzebne tylko w wydawnictwach
    ciągłych i zwartych (formularz, eksport do PBN, import z PBN).
    """

    openaccess_rok_udostepnienia = models.PositiveSmallIntegerField(
        "OpenAccess: rok udostępnienia",
        blank=True,
        null=True,
        validators=[MinValueValidator(OPENACCESS_ROK_MIN)],
        help_text="Rok udostępnienia w otwartym dostępie — razem z miesiącem, "
        "gdy nie jest znana pełna data udostępnienia.",
    )

    openaccess_miesiac_udostepnienia = models.PositiveSmallIntegerField(
        "OpenAccess: miesiąc udostępnienia",
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Miesiąc (1–12) udostępnienia w otwartym dostępie — razem "
        "z rokiem, gdy nie jest znana pełna data udostępnienia.",
    )

    class Meta:
        abstract = True

    def clean(self):
        rok = self.openaccess_rok_udostepnienia
        miesiac = self.openaccess_miesiac_udostepnienia
        if rok is None and miesiac is None:
            return

        if getattr(self, "openaccess_data_opublikowania", None) is not None:
            komunikat = (
                "Podaj albo pełną datę udostępnienia w otwartym dostępie, "
                "albo miesiąc i rok — nie oba naraz."
            )
            raise ValidationError(
                {
                    "openaccess_data_opublikowania": komunikat,
                    "openaccess_rok_udostepnienia": komunikat,
                    "openaccess_miesiac_udostepnienia": komunikat,
                }
            )

        if miesiac is None:
            raise ValidationError(
                {
                    "openaccess_miesiac_udostepnienia": (
                        "PBN wymaga co najmniej miesiąca i roku udostępnienia "
                        "— sam rok nie wystarczy. Podaj też miesiąc."
                    )
                }
            )

        if rok is None:
            raise ValidationError(
                {
                    "openaccess_rok_udostepnienia": (
                        "Podano miesiąc udostępnienia bez roku. Podaj też rok."
                    )
                }
            )

        # Zakresy sprawdzane także tutaj, nie tylko walidatorami pól: część
        # modeli publikacji nadpisuje ``clean_fields`` bez wołania ``super()``.
        if not 1 <= miesiac <= 12:
            raise ValidationError(
                {
                    "openaccess_miesiac_udostepnienia": (
                        f"Miesiąc udostępnienia {miesiac} jest nieprawidłowy "
                        "— dopuszczalne wartości to 1–12."
                    )
                }
            )

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

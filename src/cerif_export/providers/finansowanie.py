"""Provider setu ``openaire_cris_funding``.

Zakres jest ten sam co dla projektów, tylko o jeden przeskok dalej:
finansowanie należy do tenanta przez ``projekt__jednostka__uczelnia``.
Warunek musi być dokładnie taki sam jak w
:func:`cerif_export.providers.projekty.widoczne_projekty`, bo
``Project/Funded/As`` osadza pełne ``<Funding>`` z ``@id``. Rozjazd między
tymi dwoma filtrami dałby referencję do rekordu, którego harvester nigdy
nie zobaczy.
"""

from bpp.models.projekt import Finansowanie
from cerif_export import const
from cerif_export.identyfikatory import BlednyIdentyfikator
from cerif_export.kontekst import ZbioryWidocznosci
from cerif_export.providers.base import ProviderEncji
from cerif_export.providers.jednostki import (
    widoczne_pk,
    widoczni_grantodawcy,
    wymagaj_uczelni,
)


def widoczne_finansowania(uczelnia):
    """Finansowania eksportowane dla tej uczelni — bez prefetchy."""
    wymagaj_uczelni(uczelnia)
    return Finansowanie.objects.filter(projekt__jednostka__uczelnia=uczelnia)


def nalezace_finansowania(uczelnia):
    """Finansowania projektów TEJ uczelni. Jak projekty: czysta atrybucja,
    dopełnienie puste."""
    wymagaj_uczelni(uczelnia)
    return Finansowanie.objects.filter(projekt__jednostka__uczelnia=uczelnia)


class ProviderFinansowania(ProviderEncji):
    """Źródła finansowania projektów tej uczelni."""

    set_spec = const.SET_FUNDING
    typ_cerif = const.TYP_FUNDING
    modele = [Finansowanie]

    def queryset(self, uczelnia, model):
        wymagaj_uczelni(uczelnia)
        if model is not Finansowanie:
            raise BlednyIdentyfikator(
                f"Model {model!r} nie należy do setu {self.set_spec}"
            )

        return widoczne_finansowania(uczelnia).select_related("instytucja")

    def przynaleznosc(self, uczelnia, model):
        wymagaj_uczelni(uczelnia)
        if model is not Finansowanie:
            raise BlednyIdentyfikator(
                f"Model {model!r} nie należy do setu {self.set_spec}"
            )

        return nalezace_finansowania(uczelnia).select_related("instytucja")

    def zbiory_widocznosci(self, uczelnia, obiekty) -> ZbioryWidocznosci:
        """Prekomputuj widoczność grantodawców osadzanych w ``Funder``."""
        wymagaj_uczelni(uczelnia)

        grantodawcy = {finansowanie.instytucja_id for finansowanie in obiekty}
        return ZbioryWidocznosci(
            grantodawcy=widoczne_pk(widoczni_grantodawcy(uczelnia), grantodawcy)
        )

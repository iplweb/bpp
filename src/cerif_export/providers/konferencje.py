"""Provider setu ``openaire_cris_events``.

``Konferencja`` to słownik **współdzielony** między uczelniami — nie ma FK do
uczelni ani pola opt-out. Widoczna jest wyłącznie wtedy, gdy wskazuje na nią
eksportowana publikacja tego tenanta; predykat mieszka w ``publikacje.py``,
bo jest pochodną reguł widoczności publikacji.
"""

from bpp.models.konferencja import Konferencja
from cerif_export import const
from cerif_export.identyfikatory import BlednyIdentyfikator
from cerif_export.kontekst import ZbioryWidocznosci
from cerif_export.providers.base import ProviderEncji
from cerif_export.providers.jednostki import wymagaj_uczelni
from cerif_export.providers.publikacje import (
    nalezace_konferencje,
    widoczne_konferencje,
)


class ProviderKonferencji(ProviderEncji):
    """Konferencje użyte przez eksportowane publikacje."""

    set_spec = const.SET_EVENTS
    typ_cerif = const.TYP_EVENT
    modele = [Konferencja]

    def queryset(self, uczelnia, model):
        wymagaj_uczelni(uczelnia)
        if model is not Konferencja:
            raise BlednyIdentyfikator(
                f"Model {model!r} nie należy do setu {self.set_spec}"
            )
        return widoczne_konferencje(uczelnia).select_related("pbn_uid")

    def przynaleznosc(self, uczelnia, model):
        wymagaj_uczelni(uczelnia)
        if model is not Konferencja:
            raise BlednyIdentyfikator(
                f"Model {model!r} nie należy do setu {self.set_spec}"
            )
        return nalezace_konferencje(uczelnia).select_related("pbn_uid")

    def zbiory_widocznosci(self, uczelnia, obiekty) -> ZbioryWidocznosci:
        """Konferencja nie osadza encji sąsiadujących — zbiory są puste."""
        wymagaj_uczelni(uczelnia)
        return ZbioryWidocznosci()

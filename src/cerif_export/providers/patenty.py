"""Provider setu ``openaire_cris_patents``.

Patent jest w CERIF **osobną encją** w osobnym secie — dlatego enumeracja
publikacji nie może iść po widoku ``bpp_rekord``, który unionuje patenty
razem z wydawnictwami.
"""

from django.db.models import Prefetch

from bpp.models.patent import Patent, Patent_Autor
from cerif_export import const
from cerif_export.identyfikatory import BlednyIdentyfikator
from cerif_export.kontekst import ZbioryWidocznosci
from cerif_export.providers.base import ProviderEncji
from cerif_export.providers.jednostki import (
    widoczne_jednostki,
    widoczne_pk,
    wymagaj_uczelni,
)
from cerif_export.providers.osoby import widoczni_autorzy


def widoczne_patenty(uczelnia):
    """Patenty eksportowane dla tej uczelni — bez prefetchy.

    Reguła jak dla wydawnictw: status korekty niewykluczony kanałem
    ``cerif``, ``nie_eksportuj_przez_api=False`` i scope tenanta przez model
    autorstwa (``Patent_Autor``).
    """
    wymagaj_uczelni(uczelnia)
    return (
        Patent.objects.exclude(
            status_korekty_id__in=uczelnia.ukryte_statusy("cerif")
        )
        .filter(nie_eksportuj_przez_api=False)
        .filter(
            pk__in=Patent_Autor.objects.filter(
                jednostka__uczelnia=uczelnia
            ).values("rekord_id")
        )
    )


PREFETCH_TWORCOW = Prefetch(
    "autorzy_set",
    queryset=Patent_Autor.objects.select_related(
        "autor", "jednostka", "typ_odpowiedzialnosci"
    ).order_by("kolejnosc"),
)


class ProviderPatentow(ProviderEncji):
    """Patenty i prawa ochronne."""

    set_spec = const.SET_PATENTS
    typ_cerif = const.TYP_PATENT
    modele = [Patent]

    def queryset(self, uczelnia, model):
        wymagaj_uczelni(uczelnia)
        if model is not Patent:
            raise BlednyIdentyfikator(
                f"Model {model!r} nie należy do setu {self.set_spec}"
            )

        return (
            widoczne_patenty(uczelnia)
            .select_related("rodzaj_prawa", "status_korekty", "wydzial")
            .prefetch_related("slowa_kluczowe", PREFETCH_TWORCOW)
        )

    def zbiory_widocznosci(self, uczelnia, obiekty) -> ZbioryWidocznosci:
        """Prekomputuj widoczność twórców (``Inventors``) i ich jednostek."""
        wymagaj_uczelni(uczelnia)

        autorzy, jednostki = set(), set()
        for patent in obiekty:
            jednostki.add(patent.wydzial_id)
            for autorstwo in patent.autorzy_set.all():
                autorzy.add(autorstwo.autor_id)
                jednostki.add(autorstwo.jednostka_id)

        return ZbioryWidocznosci(
            autorzy=widoczne_pk(widoczni_autorzy(uczelnia), autorzy),
            jednostki=widoczne_pk(widoczne_jednostki(uczelnia), jednostki),
        )

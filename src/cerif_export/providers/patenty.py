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
    widoczni_grantodawcy,
    wymagaj_uczelni,
)
from cerif_export.providers.osoby import widoczni_autorzy
from cerif_export.providers.projekty import (
    klucze_osadzonych_projektow,
    prefetche_pochodzenia,
)


def widoczne_patenty(uczelnia):
    """Patenty eksportowane dla tej uczelni — bez prefetchy.

    Reguła jak dla wydawnictw: status korekty niewykluczony kanałem
    ``cerif``, ``nie_eksportuj_przez_api=False`` i scope tenanta przez model
    autorstwa (``Patent_Autor``).

    Dodatkowo odpadają rekordy o rodzaju prawa oznaczonym
    ``eksportuj_jako_patent=False`` (np. znak towarowy). ``Patent/Type`` jest
    w profilu obowiązkowy i ograniczony do gałęzi „patent" słownika COAR —
    samo pominięcie mapowania NIE dawało tu „braku typu", tylko fallback na
    ``c_15cd patent``, czyli deklarowanie znaku towarowego patentem.
    Rekordy z ``rodzaj_prawa=NULL`` zostają: to są prawdziwe patenty bez
    doprecyzowanego rodzaju, a nie inne prawa własności przemysłowej.
    """
    wymagaj_uczelni(uczelnia)
    return (
        Patent.objects.exclude(status_korekty_id__in=uczelnia.ukryte_statusy("cerif"))
        .filter(nie_eksportuj_przez_api=False)
        .exclude(rodzaj_prawa__eksportuj_jako_patent=False)
        .filter(
            pk__in=Patent_Autor.objects.filter(jednostka__uczelnia=uczelnia).values(
                "rekord_id"
            )
        )
    )


def nalezace_patenty(uczelnia):
    """Patenty TEJ uczelni — bez reguł ekspozycji.

    Scope przez model autorstwa z KOSZEM (``global_objects``), jak
    wydawnictwa; sam ``Patent`` też przez ``global_objects``, bo jest
    soft-delete od fazy 02. ``status_korekty``, ``nie_eksportuj_przez_api``
    i ``rodzaj_prawa.eksportuj_jako_patent`` to ekspozycja — zostają
    w ``widoczne_patenty()``.
    """
    wymagaj_uczelni(uczelnia)
    return Patent.global_objects.filter(
        pk__in=Patent_Autor.global_objects.filter(jednostka__uczelnia=uczelnia).values(
            "rekord_id"
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
            .prefetch_related(
                "slowa_kluczowe", PREFETCH_TWORCOW, *prefetche_pochodzenia()
            )
        )

    def przynaleznosc(self, uczelnia, model):
        wymagaj_uczelni(uczelnia)
        if model is not Patent:
            raise BlednyIdentyfikator(
                f"Model {model!r} nie należy do setu {self.set_spec}"
            )

        return (
            nalezace_patenty(uczelnia)
            .select_related("rodzaj_prawa", "status_korekty", "wydzial")
            .prefetch_related(
                "slowa_kluczowe", PREFETCH_TWORCOW, *prefetche_pochodzenia()
            )
        )

    def zbiory_widocznosci(self, uczelnia, obiekty) -> ZbioryWidocznosci:
        """Prekomputuj widoczność twórców (``Inventors``), ich jednostek
        oraz encji osadzanych przez ``OriginatesFrom``."""
        wymagaj_uczelni(uczelnia)

        autorzy, jednostki = set(), set()
        for patent in obiekty:
            jednostki.add(patent.wydzial_id)
            for autorstwo in patent.autorzy_set.all():
                autorzy.add(autorstwo.autor_id)
                jednostki.add(autorstwo.jednostka_id)

        z_projektow = klucze_osadzonych_projektow(obiekty)
        autorzy |= z_projektow[0]
        jednostki |= z_projektow[1]

        return ZbioryWidocznosci(
            autorzy=widoczne_pk(widoczni_autorzy(uczelnia), autorzy),
            jednostki=widoczne_pk(widoczne_jednostki(uczelnia), jednostki),
            grantodawcy=widoczne_pk(widoczni_grantodawcy(uczelnia), z_projektow[2]),
        )

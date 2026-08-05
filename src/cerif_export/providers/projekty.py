"""Provider setu ``openaire_cris_projects``.

Przynależność projektu do tenanta niesie wyłącznie ``Projekt.jednostka`` —
model nie ma FK do uczelni, a wszystkie pozostałe relacje (zespół,
finansowanie) są słownikami współdzielonymi albo osobami, które też bywają
wieloetatowe. Dlatego filtr idzie po ``jednostka__uczelnia`` i tylko po nim.

Reguły widoczności **samej jednostki** (``widoczna``,
``nie_eksportuj_przez_api``) świadomie nie odsiewają projektu: opt-out
dotyczy jednostki jako encji organizacyjnej, a nie prowadzonych w niej
badań. Skutkiem jest jedynie brak ``Consortium/Coordinator`` w rekordzie —
serializer nie osadzi jednostki spoza zbioru widoczności.
"""

from django.db.models import Prefetch

from bpp.models.projekt import Finansowanie, Projekt, Projekt_Autor
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


def widoczne_projekty(uczelnia):
    """Projekty eksportowane dla tej uczelni — bez prefetchy."""
    wymagaj_uczelni(uczelnia)
    return Projekt.objects.filter(jednostka__uczelnia=uczelnia)


# Zespół projektu. Kolejność jest stabilna (po kluczu głównym), bo model nie
# ma pola porządkującego, a niedeterministyczna kolejność w XML-u zamieniałaby
# każdy harvest w pozorną zmianę rekordu.
PREFETCH_ZESPOLU = Prefetch(
    "projekt_autor_set",
    queryset=Projekt_Autor.objects.select_related("autor").order_by("pk"),
)

# Finansowania wraz z grantodawcami — serializer osadza pełne ``<Funding>``
# w ``Funded/As``, więc potrzebuje obiektu instytucji, nie tylko jej klucza.
PREFETCH_FINANSOWANIA = Prefetch(
    "finansowanie_set",
    queryset=Finansowanie.objects.select_related("instytucja").order_by("pk"),
)


class ProviderProjektow(ProviderEncji):
    """Projekty badawcze prowadzone w jednostkach tej uczelni."""

    set_spec = const.SET_PROJECTS
    typ_cerif = const.TYP_PROJECT
    modele = [Projekt]

    def queryset(self, uczelnia, model):
        wymagaj_uczelni(uczelnia)
        if model is not Projekt:
            raise BlednyIdentyfikator(
                f"Model {model!r} nie należy do setu {self.set_spec}"
            )

        return (
            widoczne_projekty(uczelnia)
            .select_related("jednostka")
            .prefetch_related(
                PREFETCH_ZESPOLU,
                PREFETCH_FINANSOWANIA,
                "dyscypliny",
                "slowa_kluczowe",
            )
        )

    def zbiory_widocznosci(self, uczelnia, obiekty) -> ZbioryWidocznosci:
        """Prekomputuj widoczność zespołu, jednostki realizującej i grantodawców.

        Bez zbioru grantodawców ``Funded/By`` osadzałoby ``OrgUnit`` bez
        ``@id`` — referencję, której nie da się rozwiązać na żaden rekord.
        """
        wymagaj_uczelni(uczelnia)

        autorzy, jednostki, grantodawcy = set(), set(), set()
        for projekt in obiekty:
            jednostki.add(projekt.jednostka_id)
            for powiazanie in projekt.projekt_autor_set.all():
                autorzy.add(powiazanie.autor_id)
            for finansowanie in projekt.finansowanie_set.all():
                grantodawcy.add(finansowanie.instytucja_id)

        return ZbioryWidocznosci(
            autorzy=widoczne_pk(widoczni_autorzy(uczelnia), autorzy),
            jednostki=widoczne_pk(widoczne_jednostki(uczelnia), jednostki),
            grantodawcy=widoczne_pk(widoczni_grantodawcy(uczelnia), grantodawcy),
        )

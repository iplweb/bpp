"""Provider setu ``openaire_cris_persons``.

Reguła widoczności autora ma dwa człony i **oba są konieczne**:

1. ``pokazuj=True`` — redakcyjny opt-out osoby; autor z ``pokazuj=False`` nie
   ma prawa wyjść ani jako rekord w secie, ani jako ``Person/@id`` osadzony
   przy publikacji (test wycieku osób w ``tests/test_widocznosc.py``);
2. istnieje ``Autor_Jednostka`` do jednostki tej uczelni — ``Autor`` nie ma FK
   do uczelni, więc bez tego członu instalacja multi-hosted wyeksportowałaby
   cudzych autorów jako własnych.

Człon (2) celowo patrzy na **całą historię** afiliacji (``Autor_Jednostka``),
nie na ``aktualna_jednostka`` — emerytowany pracownik nadal jest autorem
publikacji, które eksportujemy, więc musi mieć swój rekord ``Person``.
"""

from django.db.models import Prefetch

from bpp.models.autor import Autor, Autor_Jednostka
from cerif_export import const
from cerif_export.identyfikatory import BlednyIdentyfikator
from cerif_export.kontekst import ZbioryWidocznosci
from cerif_export.providers.base import ProviderEncji
from cerif_export.providers.jednostki import (
    widoczne_jednostki,
    widoczne_pk,
    wymagaj_uczelni,
)


def widoczni_autorzy(uczelnia):
    """Autorzy eksportowani dla tej uczelni — bez prefetchy."""
    wymagaj_uczelni(uczelnia)
    return Autor.objects.filter(pokazuj=True).filter(
        pk__in=Autor_Jednostka.objects.filter(
            jednostka__uczelnia=uczelnia
        ).values("autor_id")
    )


# Affiliation — komplet powiązań autor-jednostka wraz z jednostką. Serializer
# emituje ``@id`` jednostki wyłącznie gdy siedzi ona w zbiorze widoczności,
# ale nazwę/skrót osadza zawsze, więc obiekt ``Jednostka`` musi tu być.
PREFETCH_AFILIACJI = Prefetch(
    "autor_jednostka_set",
    queryset=Autor_Jednostka.objects.select_related("jednostka", "funkcja"),
)


class ProviderOsob(ProviderEncji):
    """Osoby (autorzy) powiązane z tą uczelnią."""

    set_spec = const.SET_PERSONS
    typ_cerif = const.TYP_PERSON
    modele = [Autor]

    def queryset(self, uczelnia, model):
        wymagaj_uczelni(uczelnia)
        if model is not Autor:
            raise BlednyIdentyfikator(
                f"Model {model!r} nie należy do setu {self.set_spec}"
            )

        return (
            widoczni_autorzy(uczelnia)
            .select_related("plec", "tytul", "pbn_uid", "aktualna_jednostka")
            .prefetch_related(PREFETCH_AFILIACJI)
        )

    def zbiory_widocznosci(self, uczelnia, obiekty) -> ZbioryWidocznosci:
        """Prekomputuj widoczność jednostek afiliacji."""
        wymagaj_uczelni(uczelnia)

        kandydaci = set()
        for autor in obiekty:
            for powiazanie in autor.autor_jednostka_set.all():
                kandydaci.add(powiazanie.jednostka_id)
            kandydaci.add(autor.aktualna_jednostka_id)

        return ZbioryWidocznosci(
            jednostki=widoczne_pk(widoczne_jednostki(uczelnia), kandydaci)
        )

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
    """Autorzy eksportowani dla tej uczelni — bez prefetchy.

    Wyłączenie ``Uczelnia.eksport_cerif_osoby`` zeruje ten zbiór, co działa
    w DWÓCH miejscach naraz — i o to chodzi:

    1. zestaw ``openaire_cris_persons`` robi się pusty (istnieć musi nadal,
       bo profil wymaga wszystkich dziewięciu);
    2. autorzy osadzeni w publikacjach tracą ``@id``, ORCID i afiliacje, bo
       serializery pytają o widoczność dokładnie tego zbioru.

    Gdyby punkt 2 nie zadziałał, wyłączenie zestawu byłoby pozorne: dane
    osobowe wychodziłyby dalej, tyle że okrężną drogą przez publikacje.
    """
    wymagaj_uczelni(uczelnia)

    if not uczelnia.eksport_cerif_osoby:
        return Autor.objects.none()

    return Autor.objects.filter(pokazuj=True).filter(
        pk__in=Autor_Jednostka.objects.filter(jednostka__uczelnia=uczelnia).values(
            "autor_id"
        )
    )


def nalezacy_autorzy(uczelnia):
    """Autorzy afiliowani przy TEJ uczelni — bez reguł ekspozycji.

    ⚠️ Świadomie IGNORUJEMY ``Uczelnia.eksport_cerif_osoby`` i ``pokazuj``.
    Oba są regułami ekspozycji, więc ich wyłączenie MA produkować nagrobki
    — harvester ma te osoby usunąć. Skutek uboczny (opisany w specu):
    przestawienie przełącznika wystawia nagrobki dla wszystkich autorów
    uczelni naraz. To poprawne, ale jednorazowo bardzo hałaśliwe.

    ``global_objects``, bo ``Autor`` jest soft-delete od fazy 04 — autor
    w koszu ma dostać nagrobek, a nie zniknąć po cichu.
    """
    wymagaj_uczelni(uczelnia)
    return Autor.global_objects.filter(
        pk__in=Autor_Jednostka.objects.filter(jednostka__uczelnia=uczelnia).values(
            "autor_id"
        )
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

    def przynaleznosc(self, uczelnia, model):
        wymagaj_uczelni(uczelnia)
        if model is not Autor:
            raise BlednyIdentyfikator(
                f"Model {model!r} nie należy do setu {self.set_spec}"
            )

        return (
            nalezacy_autorzy(uczelnia)
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

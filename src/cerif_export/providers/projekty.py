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

Moduł obsługuje też **drugie** miejsce, w którym projekt się pojawia:
``Publication/OriginatesFrom`` i ``Patent/OriginatesFrom`` osadzają pełne
``<Project>``. Prefetche (:func:`prefetche_pochodzenia`) i zbiory
widoczności (:func:`klucze_osadzonych_projektow`) dla tamtej ścieżki
mieszkają tutaj, a nie w providerach publikacji i patentów, bo są
pochodną tego, czego wymaga ``cerif.project.serializuj`` — dwie kopie tej
wiedzy rozjechałyby się przy pierwszym nowym elemencie projektu.
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


def nalezace_projekty(uczelnia):
    """Projekty TEJ uczelni. Czysta atrybucja — identyczna z widocznością,
    więc dopełnienie jest puste i ten set nagrobków nie wygeneruje.
    Kontrakt implementujemy dla spójności i gotowości na przyszłe reguły."""
    wymagaj_uczelni(uczelnia)
    return Projekt.objects.filter(jednostka__uczelnia=uczelnia)


def prefetche_projektu(prefiks=""):
    """Komplet prefetchy wymaganych przez ``cerif.project.serializuj``.

    Funkcja, a nie stałe, bo te same relacje trzeba założyć w DWÓCH
    miejscach: na rekordzie projektu (prefiks pusty) i o dwa przeskoki
    dalej, przy publikacji osadzającej projekt w ``OriginatesFrom``
    (prefiks ``granty_rekordu__grant__projekt__``). Rozjazd między
    kopiami tej listy nie wywala testu — daje po cichu N+1 przy pełnym
    harveście.

    Kolejność zespołu i finansowań jest stabilna (po kluczu głównym), bo
    żaden z tych modeli nie ma pola porządkującego, a niedeterministyczna
    kolejność w XML-u zamieniałaby każdy harvest w pozorną zmianę rekordu.
    """
    return [
        Prefetch(
            f"{prefiks}projekt_autor_set",
            queryset=Projekt_Autor.objects.select_related("autor").order_by("pk"),
        ),
        # Serializer osadza pełne ``<Funding>`` w ``Funded/As``, więc
        # potrzebuje obiektu instytucji, nie tylko jej klucza.
        Prefetch(
            f"{prefiks}finansowanie_set",
            queryset=Finansowanie.objects.select_related("instytucja").order_by("pk"),
        ),
        f"{prefiks}dyscypliny",
        f"{prefiks}slowa_kluczowe",
    ]


# Ścieżka od rekordu bibliograficznego do projektu: ``Grant_Rekordu`` wiąże
# rekord z numerem grantu (``GenericRelation`` na ``RekordBPPBaza``), a
# ``Grant.projekt`` — numer z projektem.
PREFIKS_PROJEKTU_REKORDU = "granty_rekordu__grant__projekt__"


def prefetche_pochodzenia():
    """Prefetche, których wymaga ``Publication``/``Patent`` ``OriginatesFrom``.

    ``select_related`` na querysecie ``Grant_Rekordu`` ściąga grant, projekt
    i jego jednostkę jednym zapytaniem na całą stronę harvestu; dalsze
    pozycje dociągają to, czego potrzebuje sam ``cerif.project.serializuj``.
    Bez kompletu każda publikacja kosztowałaby kilka dodatkowych zapytań —
    niewidoczne w teście z jednym rekordem, zabójcze przy pełnym harveście.

    Kolejność jest stabilna (po kluczu głównym ``Grant_Rekordu``), bo model
    nie ma pola porządkującego.
    """
    from bpp.models.grant import Grant_Rekordu

    return [
        Prefetch(
            "granty_rekordu",
            queryset=Grant_Rekordu.objects.select_related(
                "grant",
                "grant__projekt",
                # ``jednostka`` rozstrzyga przynależność projektu do tenanta
                # (serializer odsiewa po ``uczelnia_id``) i jest osadzana
                # jako ``Consortium/Coordinator``.
                "grant__projekt__jednostka",
            ).order_by("pk"),
        ),
        *prefetche_projektu(PREFIKS_PROJEKTU_REKORDU),
    ]


def klucze_osadzonych_projektow(obiekty):
    """Klucze encji, które osadzi ``OriginatesFrom`` — ``(autorzy,
    jednostki, grantodawcy)``.

    Bez tego zbiory widoczności providera publikacji i patentów obejmowałyby
    wyłącznie ludzi i jednostki samej publikacji — a osadzony projekt
    referuje SWÓJ zespół, SWOJĄ jednostkę realizującą i SWOICH grantodawców.
    Kierownik projektu nie musi być autorem publikacji, więc bez tego kroku
    ``Team/PrincipalInvestigator`` osadzałby ``Person`` bez ``@id``,
    a ``Funded/By`` — ``OrgUnit`` bez ``@id``.

    Kandydatów nie filtrujemy tu po uczelni: przecięcie z querysetami
    widoczności robi i tak ``widoczne_pk``, a warunek zdublowany w dwóch
    miejscach rozjeżdża się przy pierwszej zmianie.
    """
    autorzy, jednostki, grantodawcy = set(), set(), set()

    for obj in obiekty:
        powiazania = getattr(obj, "granty_rekordu", None)
        if powiazania is None:
            continue
        for powiazanie in powiazania.all():
            grant = powiazanie.grant
            if grant is None or grant.projekt_id is None:
                continue
            projekt = grant.projekt
            jednostki.add(projekt.jednostka_id)
            for czlonek in projekt.projekt_autor_set.all():
                autorzy.add(czlonek.autor_id)
            for finansowanie in projekt.finansowanie_set.all():
                grantodawcy.add(finansowanie.instytucja_id)

    return autorzy, jednostki, grantodawcy


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
            .prefetch_related(*prefetche_projektu())
        )

    def przynaleznosc(self, uczelnia, model):
        wymagaj_uczelni(uczelnia)
        if model is not Projekt:
            raise BlednyIdentyfikator(
                f"Model {model!r} nie należy do setu {self.set_spec}"
            )

        return (
            nalezace_projekty(uczelnia)
            .select_related("jednostka")
            .prefetch_related(*prefetche_projektu())
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

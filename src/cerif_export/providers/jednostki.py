"""Provider setu ``openaire_cris_orgunits``.

Set łączy trzy modele: :class:`bpp.models.jednostka.Jednostka` (slug ``je``),
:class:`bpp.models.uczelnia.Uczelnia` (slug ``uc``) oraz
:class:`bpp.models.projekt.Instytucja_Finansujaca` (slug ``if``). Uczelnia
wychodzi zawsze — i to dokładnie jedna, ta bieżąca — bo jest właścicielem
całego repozytorium (``Service/Owner`` w ``Identify``) i korzeniem drzewa
``PartOf`` jednostek.

Grantodawcy są tu, bo profil nie ma osobnej encji grantodawcy: ``Funding/Funder``
i ``Project/Funded/By`` wskazują na ``OrgUnit``. Gdyby instytucja
finansująca nie wychodziła w tym secie, referencja byłaby wisząca i
walidator odrzuciłby harvest (kontrola integralności referencyjnej 5a).

``PartOf`` bierzemy z MPTT-owego ``Jednostka.parent``, nie z
``Jednostka_Rodzic``. Ta druga to **datowana metryczka historyczna** (wiersze
``od``/``do``, wiele na jednostkę), z której denorm wylicza dopiero ``parent``
i ``wydzial``. CERIF opisuje strukturę bieżącą, więc bierzemy stan aktualny —
przy okazji jednym ``select_related`` zamiast prefetchem po tabeli historii.
"""

from bpp.models.jednostka import Jednostka
from bpp.models.projekt import Instytucja_Finansujaca
from bpp.models.uczelnia import Uczelnia
from cerif_export import const
from cerif_export.identyfikatory import BlednyIdentyfikator
from cerif_export.kontekst import ZbioryWidocznosci
from cerif_export.providers.base import ProviderEncji


def wymagaj_uczelni(uczelnia):
    """Podnieś błąd, gdy provider dostał ``None`` zamiast tenanta.

    Warstwa OAI odsiewa brak uczelni (404) zanim tu dojdzie. Cicha degradacja
    do pustego querysetu byłaby gorsza: harvest wyglądałby na poprawny, a
    zwracał zero rekordów.
    """
    if uczelnia is None:
        raise ValueError("Provider CERIF wymaga uczelni (tenanta)")
    return uczelnia


def widoczne_jednostki(uczelnia):
    """Jednostki eksportowane dla tej uczelni — bez prefetchy.

    Trzy warunki naraz: ``widoczna`` (ukrycie w serwisie ukrywa też w
    eksporcie), ``uczelnia`` (bezpośredni FK to źródło prawdy atrybucji
    tenanta) i ``nie_eksportuj_przez_api`` (jawny opt-out redakcji).
    """
    wymagaj_uczelni(uczelnia)
    return Jednostka.objects.filter(
        widoczna=True,
        uczelnia=uczelnia,
        nie_eksportuj_przez_api=False,
    )


def nalezace_jednostki(uczelnia):
    """Jednostki TEJ uczelni — bez reguł ekspozycji.

    Atrybucja to bezpośredni FK ``uczelnia``; ``widoczna``
    i ``nie_eksportuj_przez_api`` są regułami ekspozycji i zostają
    w ``widoczne_jednostki()``, żeby ich dopełnienie dało nagrobki.
    """
    wymagaj_uczelni(uczelnia)
    return Jednostka.objects.filter(uczelnia=uczelnia)


def widoczni_grantodawcy(uczelnia):
    """Instytucje finansujące eksportowane dla tej uczelni — bez prefetchy.

    Wychodzą wyłącznie grantodawcy realnie finansujący projekty tej uczelni.
    Słownik instytucji jest współdzielony przez wszystkich tenantów i ma
    kilkanaście pozycji z seeda; wypchnięcie go w całości pokazywałoby
    OpenAIRE instytucje, z którymi uczelnia nie ma nic wspólnego — i to
    w każdym z harvestów tak samo, więc agregator nie miałby jak odróżnić
    realnego powiązania od słownikowego balastu.

    Przynależność do tenanta niesie ``Projekt.jednostka`` — to jedyny
    nośnik atrybucji projektu do uczelni.
    """
    wymagaj_uczelni(uczelnia)
    return Instytucja_Finansujaca.objects.filter(
        finansowanie__projekt__jednostka__uczelnia=uczelnia
    ).distinct()


def nalezacy_grantodawcy(uczelnia):
    """Instytucje finansujące projekty TEJ uczelni.

    ⚠️ Treść jest IDENTYCZNA z ``widoczni_grantodawcy`` — i to nie pomyłka.
    Tamten helper filtruje ``finansowanie__projekt__jednostka__uczelnia``
    wprost, czyli sama atrybucja, bez żadnej reguły ekspozycji. Dopełnienie
    jest więc puste i ten model nagrobków nie wygeneruje.

    Implementujemy mimo to, bo kontrakt providera musi być kompletny
    (``test_kazdy_provider_deklaruje_przynaleznosc``), a rozdzielenie nazw
    pokazuje następnemu czytelnikowi, gdzie dopisać regułę ekspozycji, gdyby
    kiedyś powstała — wtedy nagrobki zaczną działać bez zmian w bazie.
    """
    wymagaj_uczelni(uczelnia)
    return Instytucja_Finansujaca.objects.filter(
        finansowanie__projekt__jednostka__uczelnia=uczelnia
    ).distinct()


def widoczne_pk(queryset, kandydaci) -> frozenset:
    """Przetnij zbiór kandydatów z querysetem widoczności — jednym zapytaniem.

    ``kandydaci`` bywa pełen ``None`` (nieustawione FK) — odsiewamy je przed
    zapytaniem, żeby nie generować ``IN (NULL)``.
    """
    kandydaci = {pk for pk in kandydaci if pk is not None}
    if not kandydaci:
        return frozenset()
    return frozenset(queryset.filter(pk__in=kandydaci).values_list("pk", flat=True))


class ProviderJednostek(ProviderEncji):
    """Jednostki organizacyjne uczelni, sama uczelnia i jej grantodawcy."""

    set_spec = const.SET_ORGUNITS
    typ_cerif = const.TYP_ORGUNIT
    modele = [Jednostka, Uczelnia, Instytucja_Finansujaca]

    def queryset(self, uczelnia, model):
        wymagaj_uczelni(uczelnia)

        if model is Jednostka:
            return widoczne_jednostki(uczelnia).select_related(
                "uczelnia",
                "parent",
                "wydzial",
                "rodzaj",
                "pbn_uid",
            )

        if model is Uczelnia:
            # Bieżący tenant i tylko on. Filtr po pk zamiast ``.all()``, bo w
            # instalacji multi-hosted w bazie siedzą też cudze uczelnie.
            return Uczelnia.objects.filter(pk=uczelnia.pk).select_related("site")

        if model is Instytucja_Finansujaca:
            return widoczni_grantodawcy(uczelnia)

        raise BlednyIdentyfikator(f"Model {model!r} nie należy do setu {self.set_spec}")

    def przynaleznosc(self, uczelnia, model):
        wymagaj_uczelni(uczelnia)

        if model is Jednostka:
            return nalezace_jednostki(uczelnia).select_related(
                "uczelnia",
                "parent",
                "wydzial",
                "rodzaj",
                "pbn_uid",
            )

        if model is Uczelnia:
            return Uczelnia.objects.filter(pk=uczelnia.pk).select_related("site")

        if model is Instytucja_Finansujaca:
            return nalezacy_grantodawcy(uczelnia)

        raise BlednyIdentyfikator(f"Model {model!r} nie należy do setu {self.set_spec}")

    def zbiory_widocznosci(self, uczelnia, obiekty) -> ZbioryWidocznosci:
        """Prekomputuj widoczność jednostek nadrzędnych (``PartOf``)."""
        wymagaj_uczelni(uczelnia)

        kandydaci = set()
        for obj in obiekty:
            if isinstance(obj, Jednostka):
                kandydaci.add(obj.parent_id)

        return ZbioryWidocznosci(
            jednostki=widoczne_pk(widoczne_jednostki(uczelnia), kandydaci)
        )

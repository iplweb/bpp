"""Kontrakty danych między providerami a serializerami.

Kluczowa reguła architektury: **serializer nie dotyka bazy**. Widoczność
encji sąsiadujących jest prekomputowana przez provider i wstrzykiwana tutaj
jako zbiory kluczy głównych; serializer wykonuje wyłącznie sprawdzenie
przynależności do zbioru.

Naruszenie tej reguły zamienia pełny harvest w N+1 przy setkach tysięcy
rekordów, a testy liczby zapytań przestają cokolwiek gwarantować.
"""

from dataclasses import dataclass, field

from cerif_export import identyfikatory


@dataclass(frozen=True)
class Kursor:
    """Pozycja w stronicowaniu keyset.

    ``slug`` jest obowiązkowy, bo set ``openaire_cris_publications`` łączy
    pięć modeli, a klucze główne między nimi kolidują — sama para
    ``(ts, pk)`` byłaby wieloznaczna i produkowała duplikaty albo gubiła
    rekordy na granicy strony.
    """

    slug: str
    ts: str
    pk: int


@dataclass(frozen=True)
class ZbioryWidocznosci:
    """Klucze główne encji, które faktycznie wyjdą w swoich setach.

    Serializer emituje ``@id`` osadzonej encji tylko wtedy, gdy jej klucz
    jest w odpowiednim zbiorze. Inaczej osadza ją bez identyfikatora —
    profil pozwala na to wprost ("embedded entities without internal
    identifiers are permitted").
    """

    autorzy: frozenset = field(default_factory=frozenset)
    jednostki: frozenset = field(default_factory=frozenset)
    zrodla: frozenset = field(default_factory=frozenset)
    konferencje: frozenset = field(default_factory=frozenset)
    # (slug, pk) — publikacje pochodzą z pięciu różnych modeli
    publikacje: frozenset = field(default_factory=frozenset)

    _POLA_WG_SLUGU = {
        "au": "autorzy",
        "je": "jednostki",
        "zr": "zrodla",
        "kf": "konferencje",
    }

    def zawiera(self, obj) -> bool:
        """Czy dana encja wyjdzie w swoim secie?"""
        slug = identyfikatory.slug_dla(obj)

        nazwa_pola = self._POLA_WG_SLUGU.get(slug)
        if nazwa_pola is not None:
            return obj.pk in getattr(self, nazwa_pola)

        if slug == "uc":
            # Uczelnia bieżącego tenanta wychodzi zawsze.
            return True

        return (slug, obj.pk) in self.publikacje


@dataclass(frozen=True)
class KontekstSerializacji:
    """Wszystko, czego serializer potrzebuje poza samym obiektem."""

    namespace: str
    uczelnia: object
    widoczne: ZbioryWidocznosci

    def id_dla(self, obj):
        """Identyfikator OAI albo ``None``, gdy encja nie wyjdzie w secie.

        Czyste sprawdzenie przynależności do zbioru — bez zapytań.
        """
        if obj is None or not self.widoczne.zawiera(obj):
            return None
        return identyfikatory.zbuduj(self.namespace, obj)

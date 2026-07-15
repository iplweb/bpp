"""Dopasowanie stringów twórców do rekordów ``Autor`` — reużycie
``crossref_bpp.Komparator``. Agregacja distinct-nazwisk (jeden match na
unikalny string, potem rozprowadzenie decyzji na wszystkie patenty).
"""

from collections import Counter
from dataclasses import dataclass, field

from crossref_bpp.core import Komparator, StatusPorownania
from import_sqlite.core.author_names import sort_key, split_name

MAX_KANDYDATOW = 3


@dataclass
class Candidate:
    pk: int
    label: str
    pewnosc: float
    publikacji: int


@dataclass
class DistinctAuthor:
    nazwisko_zrodlowe: str
    given: str
    family: str
    wystapien: int
    status: str
    candidates: list[Candidate] = field(default_factory=list)
    prefill_pk: int | None = None


_STATUS_MAP = {
    StatusPorownania.DOKLADNE: "DOKLADNE",
    StatusPorownania.LUZNE: "LUZNE",
    StatusPorownania.WYMAGA_INGERENCJI: "WYMAGA_INGERENCJI",
}


def match_name(nazwisko_zrodlowe: str) -> DistinctAuthor:
    given, family = split_name(nazwisko_zrodlowe)
    wynik = Komparator.porownaj_author({"family": family, "given": given})

    kandydaci = wynik.kandydaci or []
    candidates = [
        Candidate(
            pk=k.autor.pk,
            label=f"{k.autor.nazwisko} {k.autor.imiona}",
            pewnosc=round(k.pewnosc, 2),
            publikacji=k.publikacji,
        )
        for k in kandydaci[:MAX_KANDYDATOW]
    ]

    status = _STATUS_MAP.get(wynik.status, "BRAK")
    if not candidates:
        status = "BRAK"

    prefill_pk = candidates[0].pk if status == "DOKLADNE" and candidates else None

    return DistinctAuthor(
        nazwisko_zrodlowe=nazwisko_zrodlowe,
        given=given,
        family=family,
        wystapien=0,
        status=status,
        candidates=candidates,
        prefill_pk=prefill_pk,
    )


def aggregate_distinct(name_strings: list[str]) -> list[DistinctAuthor]:
    counts = Counter(s for s in name_strings if s and s.strip())
    result = []
    for nazwisko_zrodlowe, wystapien in counts.items():
        da = match_name(nazwisko_zrodlowe)
        da.wystapien = wystapien
        result.append(da)
    result.sort(key=lambda d: sort_key(d.family))
    return result

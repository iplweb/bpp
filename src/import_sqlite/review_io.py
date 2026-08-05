"""Odczyt/zapis plików CSV przeglądu (autorzy, patenty).

Czyste IO — bez ORM. UTF-8, przecinek jako separator (Numbers/Excel czytają;
git-diffowalne). ``decyzja`` wypełnia człowiek między ``scan`` a ``apply``.
"""

import csv

from import_sqlite.core.author_matching import Candidate, DistinctAuthor

_AUTORZY_HEADER = [
    "nazwisko_zrodlowe",
    "given",
    "family",
    "wystapien",
    "status",
    "kandydat_1",
    "kandydat_2",
    "kandydat_3",
    "decyzja",
]

_PATENTY_HEADER = [
    "source_id",
    "numer_prawa",
    "numer_zgloszenia",
    "tytul",
    "status",
    "powod",
]


def _fmt_candidate(c: Candidate) -> str:
    return f"{c.label} (#{c.pk}, {c.pewnosc:.2f}, {c.publikacji} publ.)"


def write_authors_csv(path: str, authors: list[DistinctAuthor]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(_AUTORZY_HEADER)
        for a in authors:
            kand = [_fmt_candidate(c) for c in a.candidates]
            kand += [""] * (3 - len(kand))
            decyzja = str(a.prefill_pk) if a.prefill_pk else ""
            w.writerow(
                [a.nazwisko_zrodlowe, a.given, a.family, a.wystapien, a.status]
                + kand[:3]
                + [decyzja]
            )


def read_authors_decisions(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("nazwisko_zrodlowe") or "").strip()
            if name:
                out[name] = (row.get("decyzja") or "").strip()
    return out


def write_patents_csv(path: str, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_PATENTY_HEADER)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in _PATENTY_HEADER})

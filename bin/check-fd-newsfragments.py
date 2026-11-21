#!/usr/bin/env python
"""Pilnuje, żeby każdy ticket Freshdesk z tytułu PR-a miał newsfragment.

PR naprawiający zgłoszenie z Freshdesku ma w tytule ``FD#<numer>`` (jeden
lub kilka). Dla każdego numeru w zmianach PR-a musi być plik
``src/bpp/newsfragments/fd<numer>.<typ>.rst`` (albo ``.md``) — bez niego
poprawka nie trafi do ``HISTORY.md``, a po wydaniu nie ma czego pokazać
klientowi.

Uruchamiany w CI (workflow ``Newsfragments``) z korzenia repo:

    check-fd-newsfragments.py "<tytuł PR>" <plik ze zmienionymi ścieżkami>

Zwraca 0, gdy wszystko jest, 1 z listą brakujących numerów. Świadomy
wyjątek: etykieta ``bez-newsfragmentu`` na PR-ze (sprawdzana w workflow).
Tylko stdlib.
"""

from __future__ import annotations

import re
import sys
from pathlib import PurePosixPath

KATALOG = "src/bpp/newsfragments"
TYPY = ("feature", "bugfix", "doc", "removal")

_FD = re.compile(r"\bFD\s*#?\s*(\d+)", re.IGNORECASE)


def numery_fd(tytul: str) -> list[str]:
    """Numery zgłoszeń z tytułu PR-a, bez powtórzeń, w kolejności."""
    return list(dict.fromkeys(_FD.findall(tytul)))


def numery_z_fragmentami(sciezki: list[str]) -> set[str]:
    wynik = set()
    for sciezka in sciezki:
        p = PurePosixPath(sciezka.strip())
        if str(p.parent) != KATALOG:
            continue
        czesci = p.name.split(".")
        if len(czesci) < 3 or czesci[-1] not in ("rst", "md"):
            continue
        if czesci[-2] not in TYPY:
            continue
        m = re.fullmatch(r"fd(\d+)(?:[-_].*)?", czesci[0], re.IGNORECASE)
        if m:
            wynik.add(m.group(1))
    return wynik


def brakujace(tytul: str, sciezki: list[str]) -> list[str]:
    obecne = numery_z_fragmentami(sciezki)
    return [n for n in numery_fd(tytul) if n not in obecne]


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    tytul = argv[1]
    with open(argv[2], encoding="utf-8") as f:
        sciezki = [line for line in f.read().splitlines() if line.strip()]
    braki = brakujace(tytul, sciezki)
    if not braki:
        print(f"OK: newsfragmenty dla {numery_fd(tytul) or 'brak FD# w tytule'}")
        return 0
    for numer in braki:
        print(
            f"::error::Brak newsfragmentu dla FD#{numer}: dodaj "
            f"{KATALOG}/fd{numer}.<{'|'.join(TYPY)}>.rst "
            "(dokładny opis zmiany dla redaktora), albo dodaj etykietę "
            "'bez-newsfragmentu', jeśli to świadomy wyjątek."
        )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

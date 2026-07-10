"""Rozbicie sklejonej komórki „tytuł+imię+nazwisko" (§7 spec).

Czysty rdzeń — bez ORM. Słowniki tytułów/imion oraz callable ``probuj_match``
(sygnał bazodanowy) są wstrzykiwane; adapter (``parsers.leksykony``) dostarcza
realne wartości z bazy. Testy tabelaryczne odpalają rdzeń z atrapami.
"""

from collections.abc import Callable
from dataclasses import dataclass

CONF_HIGH = "high"
CONF_MEDIUM = "medium"
CONF_LOW = "low"

# Maksymalna długość frazy tytułu (w tokenach), np. „prof. dr hab. n. med." = 5.
_MAX_TYTUL_TOKENOW = 6


@dataclass(frozen=True)
class WynikRozbicia:
    tytul: str | None
    imiona: str
    nazwisko: str
    confidence: str
    alternatywy: list[dict]


def _jest_wersalikiem(token: str) -> bool:
    """Token ALL-CAPS o długości > 1 z co najmniej jedną literą (nie inicjał)."""
    return len(token) > 1 and token.isupper() and any(c.isalpha() for c in token)


def _dopasuj_od_przodu(tokeny_lower: list[str], tytuly: set[str]) -> int:
    for dlugosc in range(min(_MAX_TYTUL_TOKENOW, len(tokeny_lower)), 0, -1):
        if " ".join(tokeny_lower[:dlugosc]) in tytuly:
            return dlugosc
    return 0


def _dopasuj_od_tylu(tokeny_lower: list[str], tytuly: set[str]) -> int:
    n = len(tokeny_lower)
    for dlugosc in range(min(_MAX_TYTUL_TOKENOW, n), 0, -1):
        if " ".join(tokeny_lower[n - dlugosc :]) in tytuly:
            return dlugosc
    return 0


def _zdejmij_tytuly(tokeny: list[str], tytuly: set[str]):
    """Iteracyjnie zdejmuje najdłuższe dopasowania tytułów z obu stron. Zwraca
    (start, koniec, fragmenty) — plaster ``tokeny[start:koniec]`` to tokeny nazwy,
    ``fragmenty`` to usunięte frazy tytułu (oryginalna wielkość liter)."""
    start = 0
    koniec = len(tokeny)
    fragmenty: list[str] = []
    # Guard #512 F1: nie zdejmuj dopasowania tytułu, jeśli zostałoby < 2 tokenów
    # nazwy. Jednowyrazowe nazwy tytułów z bazy (`doktor`, `lekarz`, `magister`,
    # `profesor`) KOLIDUJĄ z realnymi polskimi nazwiskami — bez tego guardu
    # „Anna Doktor"/„Jan Lekarz" (poprawna para imię+nazwisko) traci część jako
    # „tytuł", zostaje 1 token → puste imię → `XLSParseError` wywala CAŁY plik.
    # Preferujemy interpretację „to nazwisko/imię" (rozstrzygną sygnały 1-5).
    while start < koniec:
        lower = [t.lower() for t in tokeny[start:koniec]]
        d = _dopasuj_od_przodu(lower, tytuly)
        if d == 0 or (koniec - (start + d)) < 2:
            break
        fragmenty.append(" ".join(tokeny[start : start + d]))
        start += d
    while koniec > start:
        lower = [t.lower() for t in tokeny[start:koniec]]
        d = _dopasuj_od_tylu(lower, tytuly)
        if d == 0 or ((koniec - d) - start) < 2:
            break
        fragmenty.append(" ".join(tokeny[koniec - d : koniec]))
        koniec -= d
    return start, koniec, fragmenty


def rozbij_osobe(
    tekst: str,
    *,
    tytuly: set[str],
    imiona_znane: set[str],
    probuj_match: Callable[[str, str], bool],
) -> WynikRozbicia:
    """Rozbija ``tekst`` na tytuł/imiona/nazwisko wg hierarchii sygnałów §7."""
    surowe = (tekst or "").split()
    flagi_przecinka = [t.endswith(",") for t in surowe]
    tokeny = [t.rstrip(",") for t in surowe]

    start, koniec, fragmenty = _zdejmij_tytuly(tokeny, tytuly)
    tytul = " ".join(fragmenty) if fragmenty else None

    nazwy = tokeny[start:koniec]
    flagi = flagi_przecinka[start:koniec]

    if not nazwy:
        return WynikRozbicia(tytul, "", "", CONF_LOW, [])
    if len(nazwy) == 1:
        return WynikRozbicia(tytul, "", nazwy[0], CONF_LOW, [])

    # Sygnał 1: przecinek → nazwisko przed przecinkiem (high).
    k = next((i for i, f in enumerate(flagi) if f), None)
    if k is not None and k + 1 < len(nazwy):
        return WynikRozbicia(
            tytul, " ".join(nazwy[k + 1 :]), " ".join(nazwy[: k + 1]), CONF_HIGH, []
        )

    # Sygnał 2: WERSALIKI wśród mixed-case → nazwisko (high).
    wersaliki = [i for i, t in enumerate(nazwy) if _jest_wersalikiem(t)]
    if len(wersaliki) == 1:
        j = wersaliki[0]
        imiona = " ".join(nazwy[:j] + nazwy[j + 1 :])
        return WynikRozbicia(tytul, imiona, nazwy[j], CONF_HIGH, [])

    # Sygnał 3: match do bazy obu hipotez — dokładnie jedna True wygrywa (high).
    a = probuj_match(" ".join(nazwy[:-1]), nazwy[-1])
    b = probuj_match(" ".join(nazwy[1:]), nazwy[0])
    if a and not b:
        return WynikRozbicia(tytul, " ".join(nazwy[:-1]), nazwy[-1], CONF_HIGH, [])
    if b and not a:
        return WynikRozbicia(tytul, " ".join(nazwy[1:]), nazwy[0], CONF_HIGH, [])

    # Sygnał 4: leksykon imion — znane → imiona, reszta → nazwisko (medium).
    znane_idx = {i for i, t in enumerate(nazwy) if t.lower() in imiona_znane}
    if znane_idx and len(znane_idx) < len(nazwy):
        imiona = " ".join(nazwy[i] for i in range(len(nazwy)) if i in znane_idx)
        nazwisko = " ".join(nazwy[i] for i in range(len(nazwy)) if i not in znane_idx)
        return WynikRozbicia(tytul, imiona, nazwisko, CONF_MEDIUM, [])

    # Sygnał 5: token z dywizem → prawdopodobnie nazwisko dwuczłonowe (medium).
    dyw_idx = [i for i, t in enumerate(nazwy) if "-" in t or "—" in t]
    if len(dyw_idx) == 1:
        j = dyw_idx[0]
        imiona = " ".join(nazwy[:j] + nazwy[j + 1 :])
        return WynikRozbicia(tytul, imiona, nazwy[j], CONF_MEDIUM, [])

    # Fallback bez sygnału: ostatni token = nazwisko (low) + alternatywa odwrócona.
    alternatywy = [
        {
            "imiona": " ".join(nazwy[1:]),
            "nazwisko": nazwy[0],
            "powod": "odwrócona kolejność",
        }
    ]
    return WynikRozbicia(tytul, " ".join(nazwy[:-1]), nazwy[-1], CONF_LOW, alternatywy)

"""Parser „komórki złożonej" APOŻ: ``RW-1/1 <Nazwa> WIBiOL <ogon>``.

Czysty rdzeń (bez ORM), testowalny tabelarycznie. Wynik zasila decyzję o
jednostce (skrót → ``skrot_hint`` reconcilera; nazwa → nazwa źródłowa; oddział
→ hint wydziału rozwiązywany PO skrócie w warstwie analizy).

Ograniczenie: w gałęzi BEZ oddziału końcowy ciąg tokenów all-lowercase jest
ucinany — nazwa kończąca się słowami pisanymi małą literą (np. „Studium
języków obcych") zostałaby przycięta; w danych APOŻ nie występuje (nazwy
Kapitalizowane), ale to znane ograniczenie.
"""

import re

# Skrót: RW-1/1, RN-2, RW-9 (litera(y) wielkie + myślnik + cyfry + opcjonalnie /cyfry).
_SKROT_RE = re.compile(r"^[A-ZŁŚŻĆŃÓ][A-ZŁŚŻĆŃÓ0-9]*-\d+(?:/\d+)?$")


def _jest_akronim(token):
    """Token „akronimowy" typu WIBiOL: len ≥3 i ≥2 wielkie litery."""
    wielkie = [c for c in token if c.isalpha() and c.isupper()]
    return len(token) >= 3 and len(wielkie) >= 2


def parsuj_komorke(komorka):
    """Zwraca ``{"skrot": str|None, "nazwa": str, "oddzial": str|None}``."""
    tokeny = (komorka or "").split()
    if not tokeny:
        return {"skrot": None, "nazwa": "", "oddzial": None}

    skrot = None
    start = 0
    if _SKROT_RE.match(tokeny[0]):
        skrot = tokeny[0]
        start = 1

    # Oddział = pierwszy token AKRONIMOWY PO skrócie (nie od tokenu 0 — sam
    # skrót „RW-1/1" też przechodzi heurystykę akronimu).
    oddzial = None
    oddzial_idx = None
    for i in range(start, len(tokeny)):
        if _jest_akronim(tokeny[i]):
            oddzial = tokeny[i]
            oddzial_idx = i
            break

    if oddzial_idx is not None:
        # Ogon = wszystko za oddziałem (bez patrzenia na wielkość liter).
        nazwa_tokeny = tokeny[start:oddzial_idx]
    else:
        # Brak oddziału → utnij KOŃCOWY ciąg tokenów all-lowercase (ogon-znacznik).
        nazwa_tokeny = tokeny[start:]
        while nazwa_tokeny and nazwa_tokeny[-1].islower():
            nazwa_tokeny.pop()

    return {"skrot": skrot, "nazwa": " ".join(nazwa_tokeny), "oddzial": oddzial}

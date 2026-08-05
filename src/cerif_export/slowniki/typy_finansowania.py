"""Słownik kontrolowany typów finansowania (``Funding/Type``).

``Funding/Type`` jest w profilu **obowiązkowy** i ograniczony enumeracją
z pliku schematu ``vocabularies/openaire_funding_types.xsd`` (vendorowany
w ``cerif_export/tests/xsd/``). Osiem wartości, każda jako URI postaci
``<schemat>#<kod>``.

W przeciwieństwie do słownika COAR **nie ma tu fallbacku**. Tam wartością
zapasową jest korzeń hierarchii — termin ogólny, ale prawdziwy. Tu każda
z ośmiu wartości niesie konkretne twierdzenie o naturze finansowania
(darowizna to nie przetarg), więc zgadywanie byłoby wpisywaniem nieprawdy.
Nieznana wartość daje ``None``, a decyzję co z tym zrobić podejmuje
serializer — który i tak dostaje dane z pola z ``choices``, więc do
``None`` dochodzi tylko przy ręcznej podmianie w bazie albo po zmianie
słownika w modelu bez aktualizacji tego pliku.

Funkcja jest **czysta** — nie dotyka bazy.
"""

SCHEMAT = "https://www.openaire.eu/cerif-profile/vocab/OpenAIRE_Funding_Types"

# Kod → angielski termin ze schematu. Termin nie bierze udziału w walidacji
# (ta idzie po kluczach), służy dokumentacji i czytelności raportu mapowań.
TYPY = {
    "FundingProgramme": "Funding Programme",
    "Call": "Call",
    "Tender": "Tender",
    "Gift": "Gift",
    "InternalFunding": "Internal Funding",
    "Contract": "Contract",
    "Award": "Award",
    "Grant": "Grant",
}

WSZYSTKIE = frozenset(f"{SCHEMAT}#{kod}" for kod in TYPY)


def uri_typu(typ: str) -> str | None:
    """Zwróć URI typu finansowania albo ``None`` dla nieznanej wartości.

    Porównanie jest **wrażliwe na wielkość liter** — kody w enumeracji są
    w CamelCase i schemat XSD porównuje je dosłownie, więc ``"grant"``
    dałoby dokument niepoprawny wobec profilu.
    """
    if not typ:
        return None

    kod = typ.strip()
    if kod not in TYPY:
        return None
    return f"{SCHEMAT}#{kod}"


def znany(uri) -> bool:
    """Czy URI należy do enumeracji typów finansowania z profilu?"""
    if not uri:
        return False

    return uri.strip() in WSZYSTKIE

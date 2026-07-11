"""Split i normalizacja stringów nazwisk twórców z pola ``inventors``.

Czyste funkcje — bez ORM, bez bazy. Testowalne w izolacji.
"""

import unicodedata

# Litery, których NFKD NIE rozkłada na base+diakrytyk (to osobne code-pointy),
# a które w praktyce bywają zapisywane wariantowo (ł↔l). Grupujemy je do formy
# bazowej, żeby warianty pisowni sąsiadowały w sortowaniu.
_TRANSLIT = str.maketrans(
    {"ł": "l", "Ł": "l", "ø": "o", "Ø": "o", "đ": "d", "Đ": "d", "ß": "ss"}
)


def split_name(s: str) -> tuple[str, str]:
    """Rozbij ``"Imię Nazwisko"`` na ``(given, family)``.

    Konwencja źródła (ASB): imię-najpierw. Pierwszy token to imię, cała
    reszta to nazwisko (obsługuje nazwiska wieloczłonowe i łącznikowe).
    Jeden token → traktujemy jako samo nazwisko. Puste → ``("", "")``.
    """
    tokens = (s or "").split()
    if not tokens:
        return ("", "")
    if len(tokens) == 1:
        return ("", tokens[0])
    return (tokens[0], " ".join(tokens[1:]))


def sort_key(family: str) -> str:
    """Klucz sortowania: lower, bez diakrytyków, bez znaków spoza [a-z0-9 ].

    Warianty pisowni tego samego nazwiska lądują blisko siebie w sortowaniu,
    więc człowiek widzi rozjazd (Kowalski/Kovalski) obok siebie w CSV.
    """
    text = (family or "").translate(_TRANSLIT)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    return "".join(c if c.isalnum() or c == " " else " " for c in text).strip()

"""Kontrola schematu adresów URL trafiających do linków i przekierowań.

Adresy WWW publikacji pochodzą m.in. z importów (PBN, CrossRef, BibTeX),
które zapisują rekordy przez ``objects.create()`` z pominięciem walidatora
``URLField``. Ten moduł dostarcza wspólną logikę dla modelu (czyszczenie
przy zapisie), szablonów (filtr ``bezpieczny_url``) i walidacji ``Uczelnia``.
"""

import re

#: Schematy, które wolno renderować jako link (ścisła lista dozwolonych).
SCHEMATY_LINKOW = ("http", "https")

#: Schematy, które wolno przechowywać w polu WWW (zgodne z ``URLValidator``).
SCHEMATY_PRZECHOWYWANE = ("http", "https", "ftp", "ftps")

_ZNAKI_WEWNETRZNE = re.compile(r"[\t\r\n]")
_JAWNY_SCHEMAT = re.compile(r"^([a-zA-Z][a-zA-Z0-9+\-]*):")


def normalizuj_url(url):
    """Usuń znaki, które przeglądarka i tak ignoruje w adresie URL.

    Przeglądarki obcinają wiodące/końcowe znaki kontrolne C0 i spacje oraz
    usuwają tabulatory i znaki nowej linii z wnętrza adresu.
    """
    if url is None:
        return ""
    url = str(url)
    url = "".join(c for c in url if not (ord(c) <= 0x20 and c not in "\t\r\n"))
    return _ZNAKI_WEWNETRZNE.sub("", url).strip()


def czy_bezpieczny_link(url):
    """Czy adres można wstawić jako ``href`` (tylko http/https)."""
    znormalizowany = normalizuj_url(url).lower()
    return any(znormalizowany.startswith(f"{s}://") for s in SCHEMATY_LINKOW)


def jawny_schemat(url):
    """Zwróć jawnie podany schemat adresu (małymi literami) albo ``None``."""
    m = _JAWNY_SCHEMAT.match(normalizuj_url(url))
    if m is None:
        return None
    return m.group(1).lower()


def oczysc_url_do_zapisu(url):
    """Wyczyść adres z niedozwolonym, jawnie podanym schematem.

    Adresy bez schematu (np. ``www.example.com``) zostają bez zmian — nie
    są renderowane jako link (patrz filtr ``bezpieczny_url``), a ich
    kasowanie przy dowolnym zapisie rekordu oznaczałoby utratę danych.
    """
    if not url:
        return url
    schemat = jawny_schemat(url)
    if schemat is not None and schemat not in SCHEMATY_PRZECHOWYWANE:
        return ""
    return url

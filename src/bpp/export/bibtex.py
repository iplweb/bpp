"""
BibTeX export functionality for BPP publication models.

This module provides utilities to export Wydawnictwo_Ciagle and Wydawnictwo_Zwarte
models to BibTeX format.
"""

import logging
import re

from bpp.util import zaloguj_polkniety_wyjatek

logger = logging.getLogger(__name__)


def sanitize_bibtex_string(text: str) -> str:
    """
    Sanitize a string for use in BibTeX format.

    Args:
        text: Input string to sanitize

    Returns:
        Sanitized string safe for BibTeX
    """
    if not text:
        return ""

    # Remove or replace problematic characters
    text = str(text)
    text = text.replace("{", "\\{")
    text = text.replace("}", "\\}")
    text = text.replace("&", "\\&")
    text = text.replace("%", "\\%")
    text = text.replace("$", "\\$")
    text = text.replace("#", "\\#")
    text = text.replace("_", "\\_")
    text = text.replace("^", "\\^")
    text = text.replace("~", "\\~")

    return text.strip()


def format_authors_bibtex(wydawnictwo) -> str:
    """
    Format authors for BibTeX export.

    Args:
        wydawnictwo: Wydawnictwo_Ciagle or Wydawnictwo_Zwarte instance

    Returns:
        Formatted author string for BibTeX
    """
    authors = []
    try:
        for autor_obj in wydawnictwo.autorzy_dla_opisu():
            if hasattr(autor_obj, "zapisany_jako") and autor_obj.zapisany_jako:
                authors.append(autor_obj.zapisany_jako)
            elif hasattr(autor_obj, "autor"):
                full_name = f"{autor_obj.autor.nazwisko} {autor_obj.autor.imiona}"
                authors.append(full_name)
    except Exception:
        zaloguj_polkniety_wyjatek(
            f"Formatowanie autorów do BibTeX "
            f"(wydawnictwo pk={getattr(wydawnictwo, 'pk', None)})",
            logger=logger,
        )
        # Fallback to cached authors if available
        if (
            hasattr(wydawnictwo, "opis_bibliograficzny_autorzy_cache")
            and wydawnictwo.opis_bibliograficzny_autorzy_cache
        ):
            # The cached authors are already in "LastName FirstName" format
            authors = wydawnictwo.opis_bibliograficzny_autorzy_cache

    return " and ".join(authors)


def generate_bibtex_key(wydawnictwo) -> str:
    """
    Generate a unique BibTeX citation key.

    Args:
        wydawnictwo: Wydawnictwo_Ciagle or Wydawnictwo_Zwarte instance

    Returns:
        Generated BibTeX key
    """
    # Use first author's surname if available
    key_parts = []

    try:
        first_author = wydawnictwo.autorzy_dla_opisu().first()
        if first_author and hasattr(first_author, "autor"):
            surname = first_author.autor.nazwisko
            # Clean surname for key
            surname = re.sub(r"[^a-zA-Z0-9]", "", surname)
            key_parts.append(surname)
    except Exception:
        zaloguj_polkniety_wyjatek(
            f"Generowanie klucza BibTeX z nazwiska pierwszego autora "
            f"(wydawnictwo pk={getattr(wydawnictwo, 'pk', None)})",
            logger=logger,
        )

    # Add year
    if hasattr(wydawnictwo, "rok") and wydawnictwo.rok:
        key_parts.append(str(wydawnictwo.rok))

    # Add ID as fallback or uniqueness
    key_parts.append(f"id{wydawnictwo.pk}")

    return "_".join(key_parts)


def _emit_field(name: str, raw_value, sanitize: bool = True) -> str:
    """
    Emit a single ``  name = {value},\n`` BibTeX line, or "" when empty.

    The truthiness of ``raw_value`` decides whether the field appears at all
    (mirroring the original per-field ``if value:`` guards). String values are
    escaped through :func:`sanitize_bibtex_string` unless ``sanitize`` is False
    (used for already-safe values such as the numeric ``year`` and literal
    ``type``/``note`` markers).
    """
    if not raw_value:
        return ""
    value = sanitize_bibtex_string(raw_value) if sanitize else raw_value
    return f"  {name} = {{{value}}},\n"


def _build_bibtex_entry(entry_type: str, key: str, fields) -> str:
    """
    Assemble a complete BibTeX entry from an ordered field spec.

    Args:
        entry_type: BibTeX entry type without the ``@`` (e.g. ``"article"``).
        key: Citation key.
        fields: Iterable of ``(name, raw_value, sanitize)`` tuples emitted in
            order; empty values are skipped by :func:`_emit_field`.

    Returns:
        BibTeX formatted string (trailing comma stripped, closing brace added).
    """
    bibtex_entry = f"@{entry_type}{{{key},\n"
    for name, raw_value, sanitize in fields:
        bibtex_entry += _emit_field(name, raw_value, sanitize)
    return bibtex_entry.rstrip(",\n") + "\n}\n"


def _address_from_miejsce_i_rok(miejsce_i_rok) -> str | None:
    """
    Extract the address portion from a ``miejsce_i_rok`` ("place year") field.

    A trailing 4-digit year token is dropped; the remainder is the address.
    When no trailing year is present the whole (stripped) field is the address.
    Returns ``None`` when nothing usable remains.
    """
    if not miejsce_i_rok:
        return None
    miejsce_i_rok = miejsce_i_rok.strip()
    parts = miejsce_i_rok.split()
    if not parts:
        return None
    if len(parts) > 1 and re.match(r"\d{4}", parts[-1]):
        address = " ".join(parts[:-1])
        return address or None
    return miejsce_i_rok


def _school_from_jednostka(publikacja) -> str | None:
    """Return the faculty (wydzial) name for a thesis' unit, if available."""
    jednostka = getattr(publikacja, "jednostka", None)
    if not jednostka:
        return None
    wydzial = getattr(jednostka, "wydzial", None)
    if not wydzial:
        return None
    return wydzial.nazwa


def _method_value(publikacja, method_name: str):
    """
    Call a no-arg helper method (e.g. ``numer_tomu``) and return ``str`` of a
    truthy result, else ``None`` — preserving the original ``str(method())``
    coercion guarded by a truthiness check.
    """
    method = getattr(publikacja, method_name, None)
    if method is None:
        return None
    result = method()
    return str(result) if result else None


def _attr(publikacja, name: str):
    """Return a (possibly nested) attribute or ``None`` if absent/falsy."""
    return getattr(publikacja, name, None) or None


def wydawnictwo_ciagle_to_bibtex(wydawnictwo_ciagle) -> str:
    """
    Convert Wydawnictwo_Ciagle instance to BibTeX format.

    Args:
        wydawnictwo_ciagle: Wydawnictwo_Ciagle model instance

    Returns:
        BibTeX formatted string
    """
    w = wydawnictwo_ciagle
    zrodlo = _attr(w, "zrodlo")
    fields = [
        ("title", w.tytul_oryginalny, True),
        ("author", format_authors_bibtex(w), True),
        ("journal", zrodlo.nazwa if zrodlo else None, True),
        ("year", w.rok, False),
        ("volume", _method_value(w, "numer_tomu"), True),
        ("number", _method_value(w, "numer_wydania"), True),
        ("pages", _method_value(w, "zakres_stron"), True),
        ("doi", _attr(w, "doi"), True),
        ("issn", _attr(w, "issn"), True),
        ("url", _attr(w, "www"), True),
    ]
    return _build_bibtex_entry("article", generate_bibtex_key(w), fields)


def _zwarte_entry_type(wydawnictwo_zwarte) -> str:
    """Pick the BibTeX entry type for a Wydawnictwo_Zwarte by its traits."""
    if _attr(wydawnictwo_zwarte, "wydawnictwo_nadrzedne"):
        return "incollection"  # Chapter in book
    charakter_formalny = _attr(wydawnictwo_zwarte, "charakter_formalny")
    if charakter_formalny:
        charakter = charakter_formalny.nazwa.lower()
        if "rozdział" in charakter or "chapter" in charakter:
            return "incollection"
        if "konferencja" in charakter or "conference" in charakter:
            return "inproceedings"
    return "book"


def wydawnictwo_zwarte_to_bibtex(wydawnictwo_zwarte) -> str:
    """
    Convert Wydawnictwo_Zwarte instance to BibTeX format.

    Args:
        wydawnictwo_zwarte: Wydawnictwo_Zwarte model instance

    Returns:
        BibTeX formatted string
    """
    w = wydawnictwo_zwarte
    entry_type = _zwarte_entry_type(w)
    get_wydawnictwo = getattr(w, "get_wydawnictwo", None)
    publisher = get_wydawnictwo() if get_wydawnictwo else None
    nadrzedne = _attr(w, "wydawnictwo_nadrzedne")
    booktitle = (
        nadrzedne.tytul_oryginalny
        if entry_type == "incollection" and nadrzedne
        else None
    )
    seria = _attr(w, "seria_wydawnicza")
    fields = [
        ("title", w.tytul_oryginalny, True),
        ("author", format_authors_bibtex(w), True),
        ("publisher", publisher, True),
        ("address", _address_from_miejsce_i_rok(_attr(w, "miejsce_i_rok")), True),
        ("year", w.rok, False),
        ("pages", _attr(w, "strony"), True),
        ("booktitle", booktitle, True),
        ("doi", _attr(w, "doi"), True),
        ("isbn", _attr(w, "isbn"), True),
        ("url", _attr(w, "www"), True),
        ("edition", _attr(w, "oznaczenie_wydania"), True),
        ("series", seria.nazwa if seria else None, True),
    ]
    return _build_bibtex_entry(entry_type, generate_bibtex_key(w), fields)


def _patent_note(patent) -> str | None:
    """Build the patent ``note`` field from its identifier/date attributes."""
    note_parts = []
    for attr_name, label in (
        ("numer_zgloszenia", "Numer zgłoszenia"),
        ("numer_prawa_wylacznego", "Numer prawa wyłącznego"),
        ("data_zgloszenia", "Data zgłoszenia"),
        ("data_decyzji", "Data decyzji"),
    ):
        value = _attr(patent, attr_name)
        if value:
            note_parts.append(f"{label}: {value}")
    return ". ".join(note_parts) if note_parts else None


def patent_to_bibtex(patent) -> str:
    """
    Convert Patent instance to BibTeX format.

    Args:
        patent: Patent model instance

    Returns:
        BibTeX formatted string
    """
    fields = [
        ("title", patent.tytul_oryginalny, True),
        ("author", format_authors_bibtex(patent), True),
        ("year", patent.rok, False),
        ("note", _patent_note(patent), True),
        ("url", _attr(patent, "www"), True),
    ]
    return _build_bibtex_entry("misc", generate_bibtex_key(patent), fields)


def praca_doktorska_to_bibtex(praca_doktorska) -> str:
    """
    Convert Praca_Doktorska instance to BibTeX format.

    Args:
        praca_doktorska: Praca_Doktorska model instance

    Returns:
        BibTeX formatted string
    """
    p = praca_doktorska
    fields = [
        ("title", p.tytul_oryginalny, True),
        ("author", format_authors_bibtex(p), True),
        ("school", _school_from_jednostka(p), True),
        ("year", p.rok, False),
        ("type", "Rozprawa doktorska", False),
        ("address", _address_from_miejsce_i_rok(_attr(p, "miejsce_i_rok")), True),
        ("url", _attr(p, "www"), True),
    ]
    return _build_bibtex_entry("phdthesis", generate_bibtex_key(p), fields)


def praca_habilitacyjna_to_bibtex(praca_habilitacyjna) -> str:
    """
    Convert Praca_Habilitacyjna instance to BibTeX format.

    Args:
        praca_habilitacyjna: Praca_Habilitacyjna model instance

    Returns:
        BibTeX formatted string
    """
    p = praca_habilitacyjna
    fields = [
        ("title", p.tytul_oryginalny, True),
        ("author", format_authors_bibtex(p), True),
        ("year", p.rok, False),
        ("note", "Rozprawa habilitacyjna", False),
        ("school", _school_from_jednostka(p), True),
        ("address", _address_from_miejsce_i_rok(_attr(p, "miejsce_i_rok")), True),
        ("url", _attr(p, "www"), True),
    ]
    return _build_bibtex_entry("misc", generate_bibtex_key(p), fields)


def export_to_bibtex(publications) -> str:
    """
    Export multiple publications to BibTeX format.

    Args:
        publications: Queryset or list of Wydawnictwo_Ciagle/Wydawnictwo_Zwarte/Patent/
                     Praca_Doktorska/Praca_Habilitacyjna instances

    Returns:
        Complete BibTeX file content as string
    """
    bibtex_entries = []

    for pub in publications:
        if hasattr(pub, "_meta"):
            model_name = pub._meta.model_name
            if model_name == "wydawnictwo_ciagle":
                bibtex_entries.append(wydawnictwo_ciagle_to_bibtex(pub))
            elif model_name == "wydawnictwo_zwarte":
                bibtex_entries.append(wydawnictwo_zwarte_to_bibtex(pub))
            elif model_name == "patent":
                bibtex_entries.append(patent_to_bibtex(pub))
            elif model_name == "praca_doktorska":
                bibtex_entries.append(praca_doktorska_to_bibtex(pub))
            elif model_name == "praca_habilitacyjna":
                bibtex_entries.append(praca_habilitacyjna_to_bibtex(pub))

    return "\n".join(bibtex_entries)

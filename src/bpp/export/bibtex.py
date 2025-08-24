"""
BibTeX export functionality for BPP publication models.

This module provides utilities to export Wydawnictwo_Ciagle and Wydawnictwo_Zwarte
models to BibTeX format.
"""

import re


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
        pass

    # Add year
    if hasattr(wydawnictwo, "rok") and wydawnictwo.rok:
        key_parts.append(str(wydawnictwo.rok))

    # Add ID as fallback or uniqueness
    key_parts.append(f"id{wydawnictwo.pk}")

    return "_".join(key_parts)


def wydawnictwo_ciagle_to_bibtex(wydawnictwo_ciagle) -> str:
    """
    Convert Wydawnictwo_Ciagle instance to BibTeX format.

    Args:
        wydawnictwo_ciagle: Wydawnictwo_Ciagle model instance

    Returns:
        BibTeX formatted string
    """
    key = generate_bibtex_key(wydawnictwo_ciagle)
    authors = format_authors_bibtex(wydawnictwo_ciagle)

    bibtex_entry = f"@article{{{key},\n"

    # Title
    if wydawnictwo_ciagle.tytul_oryginalny:
        title = sanitize_bibtex_string(wydawnictwo_ciagle.tytul_oryginalny)
        bibtex_entry += f"  title = {{{title}}},\n"

    # Authors
    if authors:
        bibtex_entry += f"  author = {{{sanitize_bibtex_string(authors)}}},\n"

    # Journal
    if hasattr(wydawnictwo_ciagle, "zrodlo") and wydawnictwo_ciagle.zrodlo:
        journal = sanitize_bibtex_string(wydawnictwo_ciagle.zrodlo.nazwa)
        bibtex_entry += f"  journal = {{{journal}}},\n"

    # Year
    if wydawnictwo_ciagle.rok:
        bibtex_entry += f"  year = {{{wydawnictwo_ciagle.rok}}},\n"

    # Volume (tom)
    if hasattr(wydawnictwo_ciagle, "numer_tomu") and wydawnictwo_ciagle.numer_tomu():
        volume = sanitize_bibtex_string(str(wydawnictwo_ciagle.numer_tomu()))
        bibtex_entry += f"  volume = {{{volume}}},\n"

    # Number (numer wydania/zeszytu)
    if (
        hasattr(wydawnictwo_ciagle, "numer_wydania")
        and wydawnictwo_ciagle.numer_wydania()
    ):
        number = sanitize_bibtex_string(str(wydawnictwo_ciagle.numer_wydania()))
        bibtex_entry += f"  number = {{{number}}},\n"

    # Pages
    if (
        hasattr(wydawnictwo_ciagle, "zakres_stron")
        and wydawnictwo_ciagle.zakres_stron()
    ):
        pages = sanitize_bibtex_string(str(wydawnictwo_ciagle.zakres_stron()))
        bibtex_entry += f"  pages = {{{pages}}},\n"

    # DOI
    if hasattr(wydawnictwo_ciagle, "doi") and wydawnictwo_ciagle.doi:
        doi = sanitize_bibtex_string(wydawnictwo_ciagle.doi)
        bibtex_entry += f"  doi = {{{doi}}},\n"

    # ISSN
    if hasattr(wydawnictwo_ciagle, "issn") and wydawnictwo_ciagle.issn:
        issn = sanitize_bibtex_string(wydawnictwo_ciagle.issn)
        bibtex_entry += f"  issn = {{{issn}}},\n"

    # URL
    if hasattr(wydawnictwo_ciagle, "www") and wydawnictwo_ciagle.www:
        url = sanitize_bibtex_string(wydawnictwo_ciagle.www)
        bibtex_entry += f"  url = {{{url}}},\n"

    # Remove trailing comma and newline, add closing brace
    bibtex_entry = bibtex_entry.rstrip(",\n") + "\n}\n"

    return bibtex_entry


def wydawnictwo_zwarte_to_bibtex(wydawnictwo_zwarte) -> str:
    """
    Convert Wydawnictwo_Zwarte instance to BibTeX format.

    Args:
        wydawnictwo_zwarte: Wydawnictwo_Zwarte model instance

    Returns:
        BibTeX formatted string
    """
    key = generate_bibtex_key(wydawnictwo_zwarte)
    authors = format_authors_bibtex(wydawnictwo_zwarte)

    # Determine entry type based on characteristics
    entry_type = "book"
    if (
        hasattr(wydawnictwo_zwarte, "wydawnictwo_nadrzedne")
        and wydawnictwo_zwarte.wydawnictwo_nadrzedne
    ):
        entry_type = "incollection"  # Chapter in book
    elif (
        hasattr(wydawnictwo_zwarte, "charakter_formalny")
        and wydawnictwo_zwarte.charakter_formalny
    ):
        charakter = wydawnictwo_zwarte.charakter_formalny.nazwa.lower()
        if "rozdział" in charakter or "chapter" in charakter:
            entry_type = "incollection"
        elif "konferencja" in charakter or "conference" in charakter:
            entry_type = "inproceedings"

    bibtex_entry = f"@{entry_type}{{{key},\n"

    # Title
    if wydawnictwo_zwarte.tytul_oryginalny:
        title = sanitize_bibtex_string(wydawnictwo_zwarte.tytul_oryginalny)
        bibtex_entry += f"  title = {{{title}}},\n"

    # Authors
    if authors:
        bibtex_entry += f"  author = {{{sanitize_bibtex_string(authors)}}},\n"

    # Publisher
    if (
        hasattr(wydawnictwo_zwarte, "get_wydawnictwo")
        and wydawnictwo_zwarte.get_wydawnictwo()
    ):
        publisher = sanitize_bibtex_string(wydawnictwo_zwarte.get_wydawnictwo())
        bibtex_entry += f"  publisher = {{{publisher}}},\n"

    # Year and address from miejsce_i_rok
    if (
        hasattr(wydawnictwo_zwarte, "miejsce_i_rok")
        and wydawnictwo_zwarte.miejsce_i_rok
    ):
        miejsce_i_rok = wydawnictwo_zwarte.miejsce_i_rok.strip()
        # Try to extract address and year
        parts = miejsce_i_rok.split()
        if parts:
            # Last part might be year if it's 4 digits
            if len(parts) > 1 and re.match(r"\d{4}", parts[-1]):
                # year_from_field = parts[-1]
                address = " ".join(parts[:-1])
                if address:
                    bibtex_entry += (
                        f"  address = {{{sanitize_bibtex_string(address)}}},\n"
                    )
            else:
                # Whole field as address
                bibtex_entry += (
                    f"  address = {{{sanitize_bibtex_string(miejsce_i_rok)}}},\n"
                )

    # Year
    if wydawnictwo_zwarte.rok:
        bibtex_entry += f"  year = {{{wydawnictwo_zwarte.rok}}},\n"

    # Pages
    if hasattr(wydawnictwo_zwarte, "strony") and wydawnictwo_zwarte.strony:
        pages = sanitize_bibtex_string(wydawnictwo_zwarte.strony)
        bibtex_entry += f"  pages = {{{pages}}},\n"

    # For chapters, add booktitle (parent publication)
    if (
        entry_type == "incollection"
        and hasattr(wydawnictwo_zwarte, "wydawnictwo_nadrzedne")
        and wydawnictwo_zwarte.wydawnictwo_nadrzedne
    ):
        if wydawnictwo_zwarte.wydawnictwo_nadrzedne.tytul_oryginalny:
            booktitle = sanitize_bibtex_string(
                wydawnictwo_zwarte.wydawnictwo_nadrzedne.tytul_oryginalny
            )
            bibtex_entry += f"  booktitle = {{{booktitle}}},\n"

    # DOI
    if hasattr(wydawnictwo_zwarte, "doi") and wydawnictwo_zwarte.doi:
        doi = sanitize_bibtex_string(wydawnictwo_zwarte.doi)
        bibtex_entry += f"  doi = {{{doi}}},\n"

    # ISBN
    if hasattr(wydawnictwo_zwarte, "isbn") and wydawnictwo_zwarte.isbn:
        isbn = sanitize_bibtex_string(wydawnictwo_zwarte.isbn)
        bibtex_entry += f"  isbn = {{{isbn}}},\n"

    # URL
    if hasattr(wydawnictwo_zwarte, "www") and wydawnictwo_zwarte.www:
        url = sanitize_bibtex_string(wydawnictwo_zwarte.www)
        bibtex_entry += f"  url = {{{url}}},\n"

    # Edition
    if (
        hasattr(wydawnictwo_zwarte, "oznaczenie_wydania")
        and wydawnictwo_zwarte.oznaczenie_wydania
    ):
        edition = sanitize_bibtex_string(wydawnictwo_zwarte.oznaczenie_wydania)
        bibtex_entry += f"  edition = {{{edition}}},\n"

    # Series
    if (
        hasattr(wydawnictwo_zwarte, "seria_wydawnicza")
        and wydawnictwo_zwarte.seria_wydawnicza
    ):
        series = sanitize_bibtex_string(wydawnictwo_zwarte.seria_wydawnicza.nazwa)
        bibtex_entry += f"  series = {{{series}}},\n"

    # Remove trailing comma and newline, add closing brace
    bibtex_entry = bibtex_entry.rstrip(",\n") + "\n}\n"

    return bibtex_entry


def patent_to_bibtex(patent) -> str:
    """
    Convert Patent instance to BibTeX format.

    Args:
        patent: Patent model instance

    Returns:
        BibTeX formatted string
    """
    key = generate_bibtex_key(patent)
    authors = format_authors_bibtex(patent)

    bibtex_entry = f"@misc{{{key},\n"

    # Title
    if patent.tytul_oryginalny:
        title = sanitize_bibtex_string(patent.tytul_oryginalny)
        bibtex_entry += f"  title = {{{title}}},\n"

    # Authors
    if authors:
        bibtex_entry += f"  author = {{{sanitize_bibtex_string(authors)}}},\n"

    # Year
    if patent.rok:
        bibtex_entry += f"  year = {{{patent.rok}}},\n"

    # Note with patent-specific information
    note_parts = []
    if hasattr(patent, "numer_zgloszenia") and patent.numer_zgloszenia:
        note_parts.append(f"Numer zgłoszenia: {patent.numer_zgloszenia}")

    if hasattr(patent, "numer_prawa_wylacznego") and patent.numer_prawa_wylacznego:
        note_parts.append(f"Numer prawa wyłącznego: {patent.numer_prawa_wylacznego}")

    if hasattr(patent, "data_zgloszenia") and patent.data_zgloszenia:
        note_parts.append(f"Data zgłoszenia: {patent.data_zgloszenia}")

    if hasattr(patent, "data_decyzji") and patent.data_decyzji:
        note_parts.append(f"Data decyzji: {patent.data_decyzji}")

    if note_parts:
        note = sanitize_bibtex_string(". ".join(note_parts))
        bibtex_entry += f"  note = {{{note}}},\n"

    # URL
    if hasattr(patent, "www") and patent.www:
        url = sanitize_bibtex_string(patent.www)
        bibtex_entry += f"  url = {{{url}}},\n"

    # Remove trailing comma and newline, add closing brace
    bibtex_entry = bibtex_entry.rstrip(",\n") + "\n}\n"

    return bibtex_entry


def praca_doktorska_to_bibtex(praca_doktorska) -> str:
    """
    Convert Praca_Doktorska instance to BibTeX format.

    Args:
        praca_doktorska: Praca_Doktorska model instance

    Returns:
        BibTeX formatted string
    """
    key = generate_bibtex_key(praca_doktorska)
    authors = format_authors_bibtex(praca_doktorska)

    bibtex_entry = f"@phdthesis{{{key},\n"

    # Title
    if praca_doktorska.tytul_oryginalny:
        title = sanitize_bibtex_string(praca_doktorska.tytul_oryginalny)
        bibtex_entry += f"  title = {{{title}}},\n"

    # Author
    if authors:
        bibtex_entry += f"  author = {{{sanitize_bibtex_string(authors)}}},\n"

    # School (University)
    if hasattr(praca_doktorska, "jednostka") and praca_doktorska.jednostka:
        if (
            hasattr(praca_doktorska.jednostka, "wydzial")
            and praca_doktorska.jednostka.wydzial
        ):
            school = sanitize_bibtex_string(praca_doktorska.jednostka.wydzial.nazwa)
            bibtex_entry += f"  school = {{{school}}},\n"

    # Year
    if praca_doktorska.rok:
        bibtex_entry += f"  year = {{{praca_doktorska.rok}}},\n"

    # Type
    bibtex_entry += "  type = {Rozprawa doktorska},\n"

    # Publisher/address from miejsce_i_rok
    if hasattr(praca_doktorska, "miejsce_i_rok") and praca_doktorska.miejsce_i_rok:
        miejsce_i_rok = praca_doktorska.miejsce_i_rok.strip()
        # Try to extract address and year
        parts = miejsce_i_rok.split()
        if parts:
            # Last part might be year if it's 4 digits
            if len(parts) > 1 and re.match(r"\d{4}", parts[-1]):
                address = " ".join(parts[:-1])
                if address:
                    bibtex_entry += (
                        f"  address = {{{sanitize_bibtex_string(address)}}},\n"
                    )
            else:
                # Whole field as address
                bibtex_entry += (
                    f"  address = {{{sanitize_bibtex_string(miejsce_i_rok)}}},\n"
                )

    # URL
    if hasattr(praca_doktorska, "www") and praca_doktorska.www:
        url = sanitize_bibtex_string(praca_doktorska.www)
        bibtex_entry += f"  url = {{{url}}},\n"

    # Remove trailing comma and newline, add closing brace
    bibtex_entry = bibtex_entry.rstrip(",\n") + "\n}\n"

    return bibtex_entry


def praca_habilitacyjna_to_bibtex(praca_habilitacyjna) -> str:
    """
    Convert Praca_Habilitacyjna instance to BibTeX format.

    Args:
        praca_habilitacyjna: Praca_Habilitacyjna model instance

    Returns:
        BibTeX formatted string
    """
    key = generate_bibtex_key(praca_habilitacyjna)
    authors = format_authors_bibtex(praca_habilitacyjna)

    bibtex_entry = f"@misc{{{key},\n"

    # Title
    if praca_habilitacyjna.tytul_oryginalny:
        title = sanitize_bibtex_string(praca_habilitacyjna.tytul_oryginalny)
        bibtex_entry += f"  title = {{{title}}},\n"

    # Author
    if authors:
        bibtex_entry += f"  author = {{{sanitize_bibtex_string(authors)}}},\n"

    # Year
    if praca_habilitacyjna.rok:
        bibtex_entry += f"  year = {{{praca_habilitacyjna.rok}}},\n"

    # Note indicating this is a habilitation thesis
    bibtex_entry += "  note = {Rozprawa habilitacyjna},\n"

    # School (University)
    if hasattr(praca_habilitacyjna, "jednostka") and praca_habilitacyjna.jednostka:
        if (
            hasattr(praca_habilitacyjna.jednostka, "wydzial")
            and praca_habilitacyjna.jednostka.wydzial
        ):
            school = sanitize_bibtex_string(praca_habilitacyjna.jednostka.wydzial.nazwa)
            bibtex_entry += f"  school = {{{school}}},\n"

    # Publisher/address from miejsce_i_rok
    if (
        hasattr(praca_habilitacyjna, "miejsce_i_rok")
        and praca_habilitacyjna.miejsce_i_rok
    ):
        miejsce_i_rok = praca_habilitacyjna.miejsce_i_rok.strip()
        # Try to extract address and year
        parts = miejsce_i_rok.split()
        if parts:
            # Last part might be year if it's 4 digits
            if len(parts) > 1 and re.match(r"\d{4}", parts[-1]):
                address = " ".join(parts[:-1])
                if address:
                    bibtex_entry += (
                        f"  address = {{{sanitize_bibtex_string(address)}}},\n"
                    )
            else:
                # Whole field as address
                bibtex_entry += (
                    f"  address = {{{sanitize_bibtex_string(miejsce_i_rok)}}},\n"
                )

    # URL
    if hasattr(praca_habilitacyjna, "www") and praca_habilitacyjna.www:
        url = sanitize_bibtex_string(praca_habilitacyjna.www)
        bibtex_entry += f"  url = {{{url}}},\n"

    # Remove trailing comma and newline, add closing brace
    bibtex_entry = bibtex_entry.rstrip(",\n") + "\n}\n"

    return bibtex_entry


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

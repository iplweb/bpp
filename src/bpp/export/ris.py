"""
RIS export functionality for BPP publication models.

This module mirrors :mod:`bpp.export.bibtex`: it provides per-type converters
plus a dispatcher (:func:`export_to_ris`) that turns concrete publication
instances (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte, Patent, Praca_Doktorska,
Praca_Habilitacyjna) into a RIS-formatted string.

RIS is a line-based, tag-driven format. Each line is::

    XX  - value

where ``XX`` is exactly two characters, followed by two spaces, a dash and a
space. A record opens with a ``TY`` (type) tag and closes with ``ER``. We do
not escape values (RIS has no escaping mechanism); we only strip embedded
newlines, which would otherwise break the line-based structure.
"""


def _ris_line(tag: str, value) -> str:
    """Format a single RIS line, stripping newlines from the value."""
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    return f"{tag}  - {text}"


def format_authors_ris(wydawnictwo) -> list:
    """
    Return a list of author strings for RIS export.

    Uses the same source as :func:`bpp.export.bibtex.format_authors_bibtex`
    (``autorzy_dla_opisu`` with a fallback to the cached author list), but
    returns one entry per author instead of an ``" and "``-joined string,
    because RIS emits one ``AU`` line per author.
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
        # Fallback to cached authors if available (same pattern as bibtex).
        if (
            hasattr(wydawnictwo, "opis_bibliograficzny_autorzy_cache")
            and wydawnictwo.opis_bibliograficzny_autorzy_cache
        ):
            authors = list(wydawnictwo.opis_bibliograficzny_autorzy_cache)

    return [a for a in authors if a]


def _wspolne_pola(lines: list, wydawnictwo) -> None:
    """Append TI/AU/PY lines shared by every publication type."""
    if wydawnictwo.tytul_oryginalny:
        lines.append(_ris_line("TI", wydawnictwo.tytul_oryginalny))

    for author in format_authors_ris(wydawnictwo):
        lines.append(_ris_line("AU", author))

    if getattr(wydawnictwo, "rok", None):
        lines.append(_ris_line("PY", wydawnictwo.rok))


def _dodaj_strony(lines: list, zakres) -> None:
    """Split a ``"start-end"`` page range into SP / EP lines."""
    if not zakres:
        return
    zakres = str(zakres).strip()
    if "-" in zakres:
        start, end = zakres.split("-", 1)
        start, end = start.strip(), end.strip()
        if start:
            lines.append(_ris_line("SP", start))
        if end:
            lines.append(_ris_line("EP", end))
    else:
        lines.append(_ris_line("SP", zakres))


def wydawnictwo_ciagle_to_ris(wydawnictwo_ciagle) -> str:
    """Convert a Wydawnictwo_Ciagle (article) instance to a RIS record."""
    lines = ["TY  - JOUR"]
    _wspolne_pola(lines, wydawnictwo_ciagle)

    if getattr(wydawnictwo_ciagle, "zrodlo", None):
        lines.append(_ris_line("JO", wydawnictwo_ciagle.zrodlo.nazwa))

    if hasattr(wydawnictwo_ciagle, "numer_tomu") and wydawnictwo_ciagle.numer_tomu():
        lines.append(_ris_line("VL", wydawnictwo_ciagle.numer_tomu()))

    if (
        hasattr(wydawnictwo_ciagle, "numer_wydania")
        and wydawnictwo_ciagle.numer_wydania()
    ):
        lines.append(_ris_line("IS", wydawnictwo_ciagle.numer_wydania()))

    if (
        hasattr(wydawnictwo_ciagle, "zakres_stron")
        and wydawnictwo_ciagle.zakres_stron()
    ):
        _dodaj_strony(lines, wydawnictwo_ciagle.zakres_stron())

    if getattr(wydawnictwo_ciagle, "doi", None):
        lines.append(_ris_line("DO", wydawnictwo_ciagle.doi))

    if getattr(wydawnictwo_ciagle, "issn", None):
        lines.append(_ris_line("SN", wydawnictwo_ciagle.issn))

    if getattr(wydawnictwo_ciagle, "www", None):
        lines.append(_ris_line("UR", wydawnictwo_ciagle.www))

    lines.append("ER  -")
    return "\n".join(lines)


def _typ_zwartego(wydawnictwo_zwarte) -> str:
    """Wybierz RIS-owy typ (TY) dla zwartego.

    Mirror :func:`bpp.export.bibtex.wydawnictwo_zwarte_to_bibtex`: a record
    with a parent publication (``wydawnictwo_nadrzedne``) or a
    chapter/conference ``charakter_formalny`` becomes ``CHAP``/``CONF``;
    otherwise ``BOOK``.
    """
    if getattr(wydawnictwo_zwarte, "wydawnictwo_nadrzedne", None):
        return "CHAP"
    if getattr(wydawnictwo_zwarte, "charakter_formalny", None):
        charakter = wydawnictwo_zwarte.charakter_formalny.nazwa.lower()
        if "rozdział" in charakter or "chapter" in charakter:
            return "CHAP"
        if "konferencja" in charakter or "conference" in charakter:
            return "CONF"
    return "BOOK"


def wydawnictwo_zwarte_to_ris(wydawnictwo_zwarte) -> str:
    """Convert a Wydawnictwo_Zwarte (book / chapter) instance to a RIS record."""
    ty = _typ_zwartego(wydawnictwo_zwarte)
    lines = [f"TY  - {ty}"]
    _wspolne_pola(lines, wydawnictwo_zwarte)

    if (
        hasattr(wydawnictwo_zwarte, "get_wydawnictwo")
        and wydawnictwo_zwarte.get_wydawnictwo()
    ):
        lines.append(_ris_line("PB", wydawnictwo_zwarte.get_wydawnictwo()))

    if (
        ty == "CHAP"
        and getattr(wydawnictwo_zwarte, "wydawnictwo_nadrzedne", None)
        and wydawnictwo_zwarte.wydawnictwo_nadrzedne.tytul_oryginalny
    ):
        lines.append(
            _ris_line("T2", wydawnictwo_zwarte.wydawnictwo_nadrzedne.tytul_oryginalny)
        )

    if getattr(wydawnictwo_zwarte, "strony", None):
        _dodaj_strony(lines, wydawnictwo_zwarte.strony)

    if getattr(wydawnictwo_zwarte, "doi", None):
        lines.append(_ris_line("DO", wydawnictwo_zwarte.doi))

    if getattr(wydawnictwo_zwarte, "isbn", None):
        lines.append(_ris_line("SN", wydawnictwo_zwarte.isbn))

    if getattr(wydawnictwo_zwarte, "www", None):
        lines.append(_ris_line("UR", wydawnictwo_zwarte.www))

    lines.append("ER  -")
    return "\n".join(lines)


def patent_to_ris(patent) -> str:
    """Convert a Patent instance to a RIS record (``TY  - PAT``)."""
    lines = ["TY  - PAT"]
    _wspolne_pola(lines, patent)

    note_parts = []
    if getattr(patent, "numer_zgloszenia", None):
        note_parts.append(f"Numer zgłoszenia: {patent.numer_zgloszenia}")
    if getattr(patent, "numer_prawa_wylacznego", None):
        note_parts.append(f"Numer prawa wyłącznego: {patent.numer_prawa_wylacznego}")
    if note_parts:
        lines.append(_ris_line("N1", ". ".join(note_parts)))

    if getattr(patent, "www", None):
        lines.append(_ris_line("UR", patent.www))

    lines.append("ER  -")
    return "\n".join(lines)


def praca_doktorska_to_ris(praca_doktorska) -> str:
    """Convert a Praca_Doktorska instance to a RIS record (``TY  - THES``)."""
    lines = ["TY  - THES"]
    _wspolne_pola(lines, praca_doktorska)

    if getattr(praca_doktorska, "jednostka", None) and getattr(
        praca_doktorska.jednostka, "wydzial", None
    ):
        lines.append(_ris_line("PB", praca_doktorska.jednostka.wydzial.nazwa))

    lines.append(_ris_line("M3", "Rozprawa doktorska"))

    if getattr(praca_doktorska, "www", None):
        lines.append(_ris_line("UR", praca_doktorska.www))

    lines.append("ER  -")
    return "\n".join(lines)


def praca_habilitacyjna_to_ris(praca_habilitacyjna) -> str:
    """Convert a Praca_Habilitacyjna instance to a RIS record (``TY  - THES``)."""
    lines = ["TY  - THES"]
    _wspolne_pola(lines, praca_habilitacyjna)

    if getattr(praca_habilitacyjna, "jednostka", None) and getattr(
        praca_habilitacyjna.jednostka, "wydzial", None
    ):
        lines.append(_ris_line("PB", praca_habilitacyjna.jednostka.wydzial.nazwa))

    lines.append(_ris_line("M3", "Rozprawa habilitacyjna"))

    if getattr(praca_habilitacyjna, "www", None):
        lines.append(_ris_line("UR", praca_habilitacyjna.www))

    lines.append("ER  -")
    return "\n".join(lines)


def export_to_ris(publications) -> str:
    """
    Export multiple publications to RIS format.

    Args:
        publications: Queryset or list of concrete publication instances
            (Wydawnictwo_Ciagle / Wydawnictwo_Zwarte / Patent /
            Praca_Doktorska / Praca_Habilitacyjna).

    Returns:
        Complete RIS file content as a string. Records are separated by a
        blank line.
    """
    records = []

    for pub in publications:
        if not hasattr(pub, "_meta"):
            continue
        model_name = pub._meta.model_name
        if model_name == "wydawnictwo_ciagle":
            records.append(wydawnictwo_ciagle_to_ris(pub))
        elif model_name == "wydawnictwo_zwarte":
            records.append(wydawnictwo_zwarte_to_ris(pub))
        elif model_name == "patent":
            records.append(patent_to_ris(pub))
        elif model_name == "praca_doktorska":
            records.append(praca_doktorska_to_ris(pub))
        elif model_name == "praca_habilitacyjna":
            records.append(praca_habilitacyjna_to_ris(pub))

    return "\n\n".join(records)

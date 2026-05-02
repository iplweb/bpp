"""Tworzenie rekordu publikacji w BPP na podstawie zatwierdzonej sesji.

Wywoływane z ``CreateView.post`` po przejściu wszystkich kroków wizarda.
Atomic: cały proces (publikacja + autorzy + streszczenia + linkowanie PBN)
w jednej transakcji.
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from bpp.models import (
    Status_Korekty,
    Typ_Odpowiedzialnosci,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)

from ..models import ImportedAuthor
from .helpers import _detect_language
from .pbn_check import _link_pbn_uid


def _build_abstracts_list(result):
    """Zbuduj listę streszczeń z FetchedPublication.

    Priorytet:
    1. extra["abstracts"] (z body HTML, WWW provider)
    2. result.abstract (z meta tagów / API)
    """
    abstracts = result.extra.get("abstracts")
    if abstracts:
        return abstracts
    if result.abstract:
        return [{"text": result.abstract, "language": None}]
    return []


def _resolve_jezyk(language_code):
    """Znajdź obiekt Jezyk po kodzie ISO-639 lub CrossRef."""
    if not language_code:
        return None
    from bpp.models import Jezyk

    return Jezyk.objects.filter(skrot_crossref=language_code).first()


def _create_streszczenia(session, record):
    """Utwórz rekordy streszczeń dla publikacji."""
    nd = session.normalized_data
    abstracts = nd.get("abstracts", [])

    # Fallback: pojedynczy abstract z normalized_data
    if not abstracts and nd.get("abstract"):
        abstracts = [{"text": nd["abstract"], "language": None}]

    for abstract in abstracts:
        text = abstract.get("text", "").strip()
        if not text:
            continue

        lang_code = abstract.get("language")
        if not lang_code:
            lang_code = _detect_language(text)

        jezyk = _resolve_jezyk(lang_code)

        record.streszczenia.create(
            streszczenie=text,
            jezyk_streszczenia=jezyk,
        )


def _create_wydawnictwo_ciagle(session, common_fields, normalized_data):
    """Utwórz Wydawnictwo_Ciagle."""
    common_fields["zrodlo"] = session.zrodlo
    common_fields["nr_zeszytu"] = normalized_data.get("issue") or ""
    return Wydawnictwo_Ciagle.objects.create(**common_fields)


def _create_wydawnictwo_zwarte(session, common_fields, normalized_data):
    """Utwórz Wydawnictwo_Zwarte."""
    common_fields["wydawca"] = session.wydawca
    common_fields["wydawca_opis"] = session.matched_data.get("wydawca_opis", "")
    common_fields["isbn"] = normalized_data.get("isbn") or ""
    common_fields["e_isbn"] = normalized_data.get("e_isbn") or ""

    # Wydawnictwo nadrzędne (dla rozdziałów)
    if session.wydawnictwo_nadrzedne_id:
        common_fields["wydawnictwo_nadrzedne"] = session.wydawnictwo_nadrzedne
    if session.wydawnictwo_nadrzedne_w_pbn_id:
        common_fields["wydawnictwo_nadrzedne_w_pbn"] = (
            session.wydawnictwo_nadrzedne_w_pbn
        )

    issue = normalized_data.get("issue")
    if issue:
        existing = common_fields.get("szczegoly", "")
        prefix = f"{existing}, " if existing else ""
        common_fields["szczegoly"] = f"{prefix}nr zeszytu: {issue}"

    publisher_loc = session.raw_data.get("publisher-location", "")
    year = normalized_data.get("year", "")
    if publisher_loc:
        common_fields["miejsce_i_rok"] = f"{publisher_loc} {year}"

    return Wydawnictwo_Zwarte.objects.create(**common_fields)


def _add_authors_to_record(session, record):
    """Dodaj dopasowanych autorów do rekordu."""
    authors = (
        session.authors.exclude(match_status=(ImportedAuthor.MatchStatus.UNMATCHED))
        .select_related(
            "matched_autor",
            "matched_jednostka",
            "matched_dyscyplina",
        )
        .order_by("order")
    )

    typ_aut = Typ_Odpowiedzialnosci.objects.get(skrot="aut.")

    uczelnia = Uczelnia.objects.get_default()
    obca = uczelnia.obca_jednostka if uczelnia else None

    for imported_author in authors:
        if not imported_author.matched_autor or not imported_author.matched_jednostka:
            continue

        zapisany_jako = (
            f"{imported_author.family_name} {imported_author.given_name}"
        ).strip()

        jest_obca = obca and imported_author.matched_jednostka == obca
        afiliuje = not jest_obca

        record.dodaj_autora(
            autor=imported_author.matched_autor,
            jednostka=(imported_author.matched_jednostka),
            zapisany_jako=zapisany_jako,
            typ_odpowiedzialnosci_skrot=typ_aut.skrot,
            dyscyplina_naukowa=(imported_author.matched_dyscyplina),
            afiliuje=afiliuje,
        )


@transaction.atomic
def _create_publication(session):
    """Utwórz rekord publikacji na podstawie sesji."""
    normalized_data = session.normalized_data

    if not normalized_data.get("year"):
        raise ValidationError(
            "Brak roku publikacji w danych źródłowych — nie można utworzyć "
            "rekordu. Uzupełnij rok w źródle (BibTeX/CrossRef/PBN) i spróbuj "
            "ponownie."
        )

    common_fields = {
        "tytul_oryginalny": normalized_data.get("title") or "",
        "rok": normalized_data.get("year"),
        "doi": normalized_data.get("doi"),  # DOI accepts null
        "tom": normalized_data.get("volume") or "",
        "strony": normalized_data.get("pages") or "",
        "www": normalized_data.get("url") or "",
        "issn": normalized_data.get("issn") or "",
        "e_issn": normalized_data.get("e_issn") or "",
        "slowa_kluczowe": ", ".join(
            f'"{kw}"' for kw in normalized_data.get("keywords", [])
        ),
        "adnotacje": (f"Dodano przez importer publikacji ({session.provider_name})"),
        "charakter_formalny": session.charakter_formalny,
        "jezyk": session.jezyk,
        "typ_kbn": session.typ_kbn,
        "status_korekty_id": (Status_Korekty.objects.first().pk),
    }

    # original-title z CrossRef → tytul (drugi tytuł)
    original_title = normalized_data.get("original_title")
    if original_title:
        common_fields["tytul"] = original_title

    # article-number z CrossRef → szczegoly
    article_number = normalized_data.get("article_number")
    if article_number:
        common_fields["szczegoly"] = article_number

    if session.jest_wydawnictwem_zwartym:
        record = _create_wydawnictwo_zwarte(session, common_fields, normalized_data)
    else:
        record = _create_wydawnictwo_ciagle(session, common_fields, normalized_data)

    _add_authors_to_record(session, record)
    _create_streszczenia(session, record)

    if session.zrodlo and normalized_data.get("year"):
        from bpp.models.zrodlo import (
            uzupelnij_punktacje_z_zrodla,
        )

        uzupelnij_punktacje_z_zrodla(record, session.zrodlo, normalized_data["year"])

    _link_pbn_uid(session, record)

    return record

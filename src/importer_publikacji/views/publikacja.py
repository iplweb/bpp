"""Tworzenie rekordu publikacji w BPP na podstawie zatwierdzonej sesji.

Wywoływane z ``CreateView.post`` po przejściu wszystkich kroków wizarda.
Atomic: cały proces (publikacja + autorzy + streszczenia + linkowanie PBN)
w jednej transakcji.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from bpp import const
from bpp.models import (
    Status_Korekty,
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


def _add_authors_to_record(session, record, uczelnia=None):
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

    # Rola importowanego autora (typ_ogolny) → kanoniczny skrot Typ_Odpowiedzialnosci.
    SKROT_DLA_TYPU = {const.TO_AUTOR: "aut.", const.TO_REDAKTOR: "red."}

    if uczelnia is None:
        # Uczelnia sesji (multi-hosted) — obca_jednostka jest per-uczelnia.
        uczelnia = session.uczelnia
    obca = uczelnia.obca_jednostka if uczelnia else None

    for imported_author in authors:
        if not imported_author.matched_autor or not imported_author.matched_jednostka:
            continue

        # `zapisany_jako` może być nadpisane przez użytkownika w modalu
        # edycji autora; fallback dla rekordów sprzed dodania pola.
        zapisany_jako = (
            imported_author.zapisany_jako.strip()
            or (f"{imported_author.family_name} {imported_author.given_name}").strip()
        )

        jest_obca = obca and imported_author.matched_jednostka == obca
        afiliuje = not jest_obca

        record.dodaj_autora(
            autor=imported_author.matched_autor,
            jednostka=(imported_author.matched_jednostka),
            zapisany_jako=zapisany_jako,
            typ_odpowiedzialnosci_skrot=SKROT_DLA_TYPU.get(
                imported_author.typ_ogolny, "aut."
            ),
            dyscyplina_naukowa=(imported_author.matched_dyscyplina),
            afiliuje=afiliuje,
        )


def _autorzy_bez_prawa_afiliacji(session, uczelnia=None):
    """Dopasowani autorzy sesji, którzy przy tworzeniu pracy afiliowaliby
    (``afiliuje=True``) do jednostki nieprzyjmującej afiliacji.

    Zwraca listę ``ImportedAuthor`` (pusta == brak problemów). Logika afiliacji
    (jednostka obca → ``afiliuje=False``) jest lustrem
    ``_add_authors_to_record``, żeby pre-check zgadzał się z faktycznym
    zapisem. Respektuje ``BPP_WALIDUJ_AFILIACJE_AUTOROW`` — gdy walidacja jest
    globalnie wyłączona, zwraca pustą listę (tak jak ``_waliduj_afiliacje``).
    """
    from django.conf import settings

    if not getattr(settings, "BPP_WALIDUJ_AFILIACJE_AUTOROW", True):
        return []

    if uczelnia is None:
        uczelnia = session.uczelnia
    obca = uczelnia.obca_jednostka if uczelnia else None

    authors = (
        session.authors.exclude(match_status=ImportedAuthor.MatchStatus.UNMATCHED)
        .select_related(
            "matched_autor",
            "matched_jednostka",
            "matched_jednostka__rodzaj",
        )
        .order_by("order")
    )

    problemy = []
    for imported_author in authors:
        jednostka = imported_author.matched_jednostka
        if not imported_author.matched_autor or jednostka is None:
            continue
        jest_obca = bool(obca and jednostka == obca)
        afiliuje = not jest_obca
        if afiliuje and not jednostka.przyjmuje_afiliacje():
            problemy.append(imported_author)
    return problemy


def waliduj_afiliacje_sesji(session, uczelnia=None):
    """Guard afiliacji: rzuca ``ValidationError``, gdy któryś dopasowany autor
    afiliowałby do jednostki nieprzyjmującej afiliacji (rodzaj „Wydział" itp.).

    Wołany PRZED utworzeniem pracy — synchronicznie na etapie formularza UI
    (``CreateView.post``, żeby user dostał komunikat i poprawił dopasowanie)
    oraz jako twardy guard na początku ``_create_publication`` (pokrywa też
    ścieżkę retry i wywołania programistyczne).
    """
    problemy = _autorzy_bez_prawa_afiliacji(session, uczelnia)
    if not problemy:
        return
    linie = "; ".join(
        f"{ia.matched_autor} → „{ia.matched_jednostka}”" for ia in problemy
    )
    raise ValidationError(
        "Nie można utworzyć pracy — część autorów jest przypisana z afiliacją "
        "do jednostki, która nie przyjmuje afiliacji (np. wydział). Zmień "
        "jednostkę tych autorów na przyjmującą afiliację albo dopasuj ich do "
        f"jednostki obcej: {linie}."
    )


@transaction.atomic
def _create_publication(session):
    """Utwórz rekord publikacji na podstawie sesji."""
    # Twardy guard afiliacji — przed jakimkolwiek zapisem do bazy (transakcja
    # atomowa i tak by wycofała, ale tu odmawiamy zanim cokolwiek powstanie).
    waliduj_afiliacje_sesji(session)

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

        # Pełny fill ze źródła (IF/kwartyle/SNIP + punkty_kbn); operator może
        # nadpisać punkty_kbn niżej.
        uzupelnij_punktacje_z_zrodla(record, session.zrodlo, normalized_data["year"])

    # Punktacja wybrana przez operatora w kroku „Punktacja" ma ostatnie słowo
    # (dla zwartych to jedyne źródło punkty_kbn; dla ciągłych — nadpisanie po
    # danych źródła, przy zachowaniu IF/kwartyli).
    punkty_operator = session.matched_data.get("punkty_kbn")
    if punkty_operator not in (None, ""):
        record.punkty_kbn = Decimal(str(punkty_operator))
        record.save(update_fields=["punkty_kbn"])

    _link_pbn_uid(session, record)

    return record

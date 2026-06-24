"""Renderery kroków wizarda HTMX (verify / source / authors / review).

Każdy krok ma parę funkcji:

* ``_<step>_context`` — zbuduj słownik kontekstu szablonu,
* ``_render_<step>_step`` — odpowiedź dla request-a HTMX (partial + push URL),
* ``_render_<step>_full`` — pełna strona (np. wejście GET-em na link).

Plus pomocnicze: ``_find_duplicates``, ``_is_chapter``, ``_is_crossref_data``.
"""

import json

from django.shortcuts import render
from django.urls import reverse

from bpp.const import CHARAKTER_OGOLNY_ROZDZIAL
from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from crossref_bpp.core import Komparator
from import_common.normalization import normalize_doi

from ..crossref_fields import categorize_crossref_fields
from ..dspace_fields import categorize_dspace_fields
from ..forms import SourceForm, VerifyForm
from ..models import ImportedAuthor
from .authors import _orcid_settable_qs
from .helpers import (
    STEP_AUTHORS,
    STEP_REVIEW,
    STEP_SOURCE,
    STEP_VERIFY,
    _get_crossref_mapper,
    _push_url,
    _render_full_page,
    _with_breadcrumbs_oob,
)
from .pbn_check import _check_pbn_by_doi


def _find_duplicates(session):
    """Szukaj duplikatów po DOI i tytule w tabelach publikacji.

    Zwraca listę krotek (publikacja, metoda_dopasowania) lub [].
    Szuka bezpośrednio w tabelach Wydawnictwo_Ciagle
    i Wydawnictwo_Zwarte (nie w zmaterializowanym widoku).
    """
    results = []
    seen_pks = set()

    doi = session.normalized_data.get("doi")
    if doi:
        normalized = normalize_doi(doi)
        if normalized:
            for model in (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte):
                for pub in model.objects.filter(doi__iexact=normalized)[:5]:
                    key = (type(pub).__name__, pub.pk)
                    if key not in seen_pks:
                        seen_pks.add(key)
                        results.append((pub, "DOI"))

    title = session.normalized_data.get("title", "")
    if title and len(title) >= 10:
        for model in (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte):
            for pub in model.objects.filter(tytul_oryginalny__iexact=title)[:5]:
                key = (type(pub).__name__, pub.pk)
                if key not in seen_pks:
                    seen_pks.add(key)
                    results.append((pub, "tytuł"))

    return results


def _is_crossref_data(raw_data):
    """Heurystyka: czy raw_data to JSON z CrossRef API."""
    if not raw_data or not isinstance(raw_data, dict):
        return False
    return bool({"DOI", "type"} & raw_data.keys())


def _is_chapter(session):
    """Czy sesja dotyczy rozdziału (charakter_ogolny == 'roz')."""
    return (
        session.charakter_formalny_id
        and session.charakter_formalny.charakter_ogolny == CHARAKTER_OGOLNY_ROZDZIAL
    )


# --- Verify step --------------------------------------------------------------


def _verify_context(request, session, form=None):
    """Przygotuj kontekst dla kroku weryfikacji."""
    pub_type = session.normalized_data.get("publication_type")
    mapper = _get_crossref_mapper(pub_type)

    if form is None:
        initial = {
            "typ_kbn": session.typ_kbn_id,
            "jezyk": session.jezyk_id,
        }
        # Użyj wartości sesji gdy istnieją (user już submitował)
        if session.charakter_formalny_id:
            initial["charakter_formalny"] = session.charakter_formalny_id
            initial["jest_wydawnictwem_zwartym"] = session.jest_wydawnictwem_zwartym
        elif mapper and mapper.charakter_formalny_bpp_id:
            initial["charakter_formalny"] = mapper.charakter_formalny_bpp_id
            initial["jest_wydawnictwem_zwartym"] = mapper.jest_wydawnictwem_zwartym
        form = VerifyForm(initial=initial)

    existing = _find_duplicates(session)
    pbn_result = _check_pbn_by_doi(session)

    doi = session.normalized_data.get("doi")
    suggest_crossref = bool(doi and session.provider_name != "CrossRef")

    # Diagnostyka pól z API
    raw_data = session.raw_data
    field_categories = None
    raw_json_pretty = None
    if raw_data and isinstance(raw_data, dict):
        if session.provider_name == "DSpace":
            field_categories = categorize_dspace_fields(raw_data)
        elif _is_crossref_data(raw_data):
            field_categories = categorize_crossref_fields(raw_data)
        raw_json_pretty = json.dumps(
            raw_data,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )

    return {
        "session": session,
        "form": form,
        "existing": existing,
        "auto_charakter": (
            mapper.charakter_formalny_bpp
            if mapper and mapper.charakter_formalny_bpp_id
            else None
        ),
        "auto_zwarte": (mapper.jest_wydawnictwem_zwartym if mapper else None),
        "suggest_crossref": suggest_crossref,
        "crossref_doi": doi if suggest_crossref else None,
        "pbn_result": pbn_result,
        "field_categories": field_categories,
        "raw_json_pretty": raw_json_pretty,
    }


def _render_verify_step(request, session, form=None):
    """Renderuj partial weryfikacji z HX-Push-Url."""
    ctx = _verify_context(request, session, form)
    url = reverse(
        "importer_publikacji:verify",
        kwargs={"session_id": session.pk},
    )
    response = render(request, STEP_VERIFY, ctx)
    response = _with_breadcrumbs_oob(response, request, session)
    return _push_url(response, url)


def _render_verify_full(request, session, form=None):
    """Renderuj pełną stronę z krokiem weryfikacji."""
    ctx = _verify_context(request, session, form)
    return _render_full_page(request, STEP_VERIFY, ctx)


# --- Source step --------------------------------------------------------------


def _source_initial_from_session(session):
    """Odczytaj initial z zapisanych wartości sesji."""
    initial = {}
    if session.zrodlo_id:
        initial["zrodlo"] = session.zrodlo_id
    if session.wydawca_id:
        initial["wydawca"] = session.wydawca_id
    wydawca_opis = session.matched_data.get("wydawca_opis", "")
    if wydawca_opis:
        initial["wydawca_opis"] = wydawca_opis
    if session.wydawnictwo_nadrzedne_id:
        initial["wydawnictwo_nadrzedne"] = session.wydawnictwo_nadrzedne_id
    if session.wydawnictwo_nadrzedne_w_pbn_id:
        initial["wydawnictwo_nadrzedne_w_pbn"] = session.wydawnictwo_nadrzedne_w_pbn_id
    return initial


def _source_initial_auto_match(session):
    """Auto-matching źródła i wydawcy z normalized_data."""
    initial = {}
    nd = session.normalized_data
    source_title = nd.get("source_title")
    if source_title:
        src = Komparator.porownaj_container_title(source_title)
        if src.rekord_po_stronie_bpp:
            initial["zrodlo"] = src.rekord_po_stronie_bpp.pk

    publisher = nd.get("publisher")
    if publisher:
        pub = Komparator.porownaj_publisher(publisher)
        if pub.rekord_po_stronie_bpp:
            initial["wydawca"] = pub.rekord_po_stronie_bpp.pk
        else:
            initial["wydawca_opis"] = publisher
    return initial


def _source_context(request, session, form=None):
    """Przygotuj kontekst dla kroku źródła."""
    is_chapter = _is_chapter(session)

    if form is None:
        initial = _source_initial_from_session(session)
        if not initial:
            initial = _source_initial_auto_match(session)
        form = SourceForm(initial=initial)

    return {
        "session": session,
        "form": form,
        "is_chapter": is_chapter,
        "wydawnictwo_nadrzedne_obj": (session.wydawnictwo_nadrzedne),
        "wydawnictwo_nadrzedne_w_pbn_obj": (session.wydawnictwo_nadrzedne_w_pbn),
    }


def _render_source_step(request, session, form=None):
    """Renderuj partial źródła z HX-Push-Url."""
    ctx = _source_context(request, session, form)
    url = reverse(
        "importer_publikacji:source",
        kwargs={"session_id": session.pk},
    )
    response = render(request, STEP_SOURCE, ctx)
    response = _with_breadcrumbs_oob(response, request, session)
    return _push_url(response, url)


def _render_source_full(request, session, form=None):
    """Renderuj pełną stronę z krokiem źródła."""
    ctx = _source_context(request, session, form)
    return _render_full_page(request, STEP_SOURCE, ctx)


# --- Authors step -------------------------------------------------------------


def _authors_context(request, session):
    """Przygotuj kontekst dla kroku autorów."""
    from django.db.models import Prefetch

    from ..models import ImportedAuthor_Candidate

    candidates_qs = ImportedAuthor_Candidate.objects.select_related(
        "autor", "autor__aktualna_jednostka"
    ).order_by("-pewnosc", "-publikacji_count")
    all_authors = (
        session.authors.select_related(
            "matched_autor",
            "matched_jednostka",
            "matched_dyscyplina",
        )
        .prefetch_related(Prefetch("candidates", queryset=candidates_qs))
        .all()
    )
    total = all_authors.count()

    stats = {
        "total": total,
        "matched": all_authors.exclude(
            match_status=(ImportedAuthor.MatchStatus.UNMATCHED)
        ).count(),
        "auto_exact": all_authors.filter(
            match_status=(ImportedAuthor.MatchStatus.AUTO_EXACT)
        ).count(),
        "auto_loose": all_authors.filter(
            match_status=(ImportedAuthor.MatchStatus.AUTO_LOOSE)
        ).count(),
        "manual": all_authors.filter(
            match_status=(ImportedAuthor.MatchStatus.MANUAL)
        ).count(),
        "unmatched": all_authors.filter(
            match_status=(ImportedAuthor.MatchStatus.UNMATCHED)
        ).count(),
    }

    orcid_settable_count = _orcid_settable_qs(session).count()

    return {
        "session": session,
        "authors": all_authors,
        "stats": stats,
        "orcid_settable_count": orcid_settable_count,
    }


def _render_authors_step(request, session, error=None):
    """Renderuj partial autorów z HX-Push-Url."""
    ctx = _authors_context(request, session)
    if error:
        ctx["error"] = error
    url = reverse(
        "importer_publikacji:authors",
        kwargs={"session_id": session.pk},
    )
    response = render(request, STEP_AUTHORS, ctx)
    response = _with_breadcrumbs_oob(response, request, session)
    return _push_url(response, url)


def _render_authors_full(request, session):
    """Renderuj pełną stronę z krokiem autorów."""
    ctx = _authors_context(request, session)
    return _render_full_page(request, STEP_AUTHORS, ctx)


# --- Review step --------------------------------------------------------------


def _review_context(request, session):
    """Przygotuj kontekst dla kroku przeglądu."""
    from bpp.models import Uczelnia

    authors = session.authors.select_related(
        "matched_autor",
        "matched_jednostka",
        "matched_dyscyplina",
    ).exclude(matched_autor=None)

    ctx = {
        "session": session,
        "authors": authors,
        "data": session.normalized_data,
    }

    uczelnia = Uczelnia.objects.get_for_request(request)
    if (
        uczelnia is not None
        and uczelnia.pbn_integracja
        and uczelnia.pbn_aktualizuj_na_biezaco
    ):
        ctx["show_save_and_pbn"] = True

    return ctx


def _render_review_step(request, session):
    """Renderuj partial przeglądu z HX-Push-Url."""
    ctx = _review_context(request, session)
    url = reverse(
        "importer_publikacji:review",
        kwargs={"session_id": session.pk},
    )
    response = render(request, STEP_REVIEW, ctx)
    response = _with_breadcrumbs_oob(response, request, session)
    return _push_url(response, url)


def _render_review_full(request, session):
    """Renderuj pełną stronę z krokiem przeglądu."""
    ctx = _review_context(request, session)
    return _render_full_page(request, STEP_REVIEW, ctx)

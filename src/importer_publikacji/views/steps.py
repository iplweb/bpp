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

from bpp import const
from bpp.const import CHARAKTER_OGOLNY_ROZDZIAL
from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from bpp.punktacja_sugestia import (
    RodzajBraku,
    SugestiaPunktacji,
    zaproponuj_punkty_ciagle,
    zaproponuj_punkty_zwarte,
)
from crossref_bpp.core import Komparator
from crossref_bpp.duplikaty import ostrzez_o_zduplikowanych_zrodlach
from import_common.normalization import normalize_doi

from ..crossref_fields import categorize_crossref_fields
from ..dspace_fields import categorize_dspace_fields
from ..forms import PunktacjaForm, SourceForm, VerifyForm
from ..models import ImportedAuthor, ImportSession
from .authors import _orcid_settable_qs
from .helpers import (
    STEP_AUTHORS,
    STEP_PBN,
    STEP_PUNKTACJA,
    STEP_REVIEW,
    STEP_SOURCE,
    STEP_VERIFY,
    _get_crossref_mapper,
    _push_url,
    _render_full_page,
    _with_breadcrumbs_oob,
)


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
        # Patent nie ma DOI — dopasowanie tylko po tytule (tytul_oryginalny).
        from bpp.models import Patent

        for model in (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte, Patent):
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


def _patent_verify_initial(session):
    """Round-trip-safe initial dla pól patentowych w kroku Verify.

    Czyta najpierw jawne klucze zapisane przez poprzedni submit; best-effort
    z BibTeX (dopasowanie ``rodzaj_prawa`` po nazwie ``patent_type``) stosuje
    się TYLKO gdy klucz nieobecny (pierwsze wejście). Rozróżnienie „klucz
    obecny = None" (operator wyczyścił pole) vs „klucz nieobecny" (pierwszy
    raz) chroni przed nadpisaniem wyborów operatora przy powrocie do kroku.
    """
    from .publikacja import _resolve_rodzaj_prawa

    nd = session.normalized_data
    initial = {
        "numer_zgloszenia": nd.get("patent_number"),
        "data_zgloszenia": nd.get("filing_date"),
        "numer_prawa_wylacznego": nd.get("patent_grant_number"),
        "data_decyzji": nd.get("grant_date"),
        "uprawniony": nd.get("patent_holder"),
    }
    if "rodzaj_prawa_id" in nd:
        # Jawny wybór operatora (nawet None = świadomie wyczyszczone).
        initial["rodzaj_prawa"] = nd.get("rodzaj_prawa_id")
    else:
        rp = _resolve_rodzaj_prawa(nd.get("patent_type"))
        initial["rodzaj_prawa"] = rp.pk if rp else None
    if "wdrozenie" in nd:
        initial["wdrozenie"] = nd.get("wdrozenie")
    if "wydzial_id" in nd:
        initial["wydzial"] = nd.get("wydzial_id")
    return initial


def _verify_context(request, session, form=None):
    """Przygotuj kontekst dla kroku weryfikacji."""
    pub_type = session.normalized_data.get("publication_type")
    mapper = _get_crossref_mapper(pub_type)
    is_patent = session.rodzaj_rekordu == ImportSession.RodzajRekordu.PATENT

    if form is None:
        initial = {"rok": session.normalized_data.get("year")}
        if is_patent:
            initial["rodzaj_rekordu"] = ImportSession.RodzajRekordu.PATENT
            initial.update(_patent_verify_initial(session))
        else:
            initial["typ_kbn"] = session.typ_kbn_id
            initial["jezyk"] = session.jezyk_id
            # Użyj wartości sesji gdy istnieją (user już submitował), inaczej
            # auto-podpowiedź z mappera CrossRef. rodzaj_rekordu (radio)
            # zastępuje dawny boolean jest_wydawnictwem_zwartym.
            zwarte = None
            if session.charakter_formalny_id:
                initial["charakter_formalny"] = session.charakter_formalny_id
                zwarte = session.jest_wydawnictwem_zwartym
            elif mapper and mapper.charakter_formalny_bpp_id:
                initial["charakter_formalny"] = mapper.charakter_formalny_bpp_id
                zwarte = mapper.jest_wydawnictwem_zwartym
            initial["rodzaj_rekordu"] = (
                ImportSession.RodzajRekordu.ZWARTE
                if zwarte
                else ImportSession.RodzajRekordu.CIAGLE
            )
        form = VerifyForm(initial=initial)

    existing = _find_duplicates(session)

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
        "is_patent": is_patent,
        "existing": existing,
        "auto_charakter": (
            mapper.charakter_formalny_bpp
            if mapper and mapper.charakter_formalny_bpp_id
            else None
        ),
        "auto_zwarte": (mapper.jest_wydawnictwem_zwartym if mapper else None),
        "suggest_crossref": suggest_crossref,
        "crossref_doi": doi if suggest_crossref else None,
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


def _ostrzez_o_duplikatach_zrodla(request, session):
    """Po auto-matchu źródła odeślij do deduplikatora, jeśli dopasowanie
    zablokowały zduplikowane źródła (ta sama nazwa, różne ISSN)."""
    source_title = (session.normalized_data or {}).get("source_title")
    if not source_title:
        return
    ostrzez_o_zduplikowanych_zrodlach(
        request, Komparator.porownaj_container_title(source_title)
    )


def _source_context(request, session, form=None):
    """Przygotuj kontekst dla kroku źródła."""
    is_chapter = _is_chapter(session)

    if form is None:
        initial = _source_initial_from_session(session)
        if not initial:
            initial = _source_initial_auto_match(session)
            _ostrzez_o_duplikatach_zrodla(request, session)
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
        # „Wstecz" z Autorów: patent pomija Source → cofa do Verify.
        "is_patent": session.rodzaj_rekordu == ImportSession.RodzajRekordu.PATENT,
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

    is_patent = session.rodzaj_rekordu == ImportSession.RodzajRekordu.PATENT

    # Krok wstecz z przeglądu: patent pomija PBN → cofa do punktacji; dla
    # źródeł NIE-PBN prowadzi do kroku „Sprawdź w PBN", dla źródła PBN —
    # bezpośrednio do punktacji (krok PBN pominięty).
    if is_patent or session.provider_name == "PBN":
        back_step = "punktacja"
    else:
        back_step = "pbn"
    back_step_url = reverse(
        f"importer_publikacji:{back_step}",
        kwargs={"session_id": session.pk},
    )

    ctx = {
        "session": session,
        "authors": authors,
        "data": session.normalized_data,
        "back_step_url": back_step_url,
        "is_patent": is_patent,
    }

    if is_patent:
        # Rozwiąż FK (id → obiekt) do wyświetlenia nazw na przeglądzie.
        from bpp.models import Jednostka, Rodzaj_Prawa_Patentowego

        nd = session.normalized_data
        rp_id = nd.get("rodzaj_prawa_id")
        ctx["patent_rodzaj_prawa"] = (
            Rodzaj_Prawa_Patentowego.objects.filter(pk=rp_id).first() if rp_id else None
        )
        w_id = nd.get("wydzial_id")
        ctx["patent_wydzial"] = (
            Jednostka.objects.filter(pk=w_id).first() if w_id else None
        )

    uczelnia = Uczelnia.objects.get_for_request(request)
    # Patent nie idzie do PBN — nigdy nie pokazuj „Zapisz i wyślij do PBN".
    if (
        not is_patent
        and uczelnia is not None
        and uczelnia.pbn_integracja
        and uczelnia.pbn_aktualizuj_na_biezaco
    ):
        ctx["show_save_and_pbn"] = True

    return ctx


def _render_review_step(request, session, error=None):
    """Renderuj partial przeglądu z HX-Push-Url."""
    ctx = _review_context(request, session)
    if error:
        ctx["error"] = error
    url = reverse(
        "importer_publikacji:review",
        kwargs={"session_id": session.pk},
    )
    response = render(request, STEP_REVIEW, ctx)
    response = _with_breadcrumbs_oob(response, request, session)
    return _push_url(response, url)


def _render_review_full(request, session, error=None):
    """Renderuj pełną stronę z krokiem przeglądu."""
    ctx = _review_context(request, session)
    if error:
        ctx["error"] = error
    return _render_full_page(request, STEP_REVIEW, ctx)


def _oblicz_sugestie(session):
    """Policz sugestię punktacji dla sesji (ciągłe/zwarte) + poziom wydawcy.

    Zwraca ``(SugestiaPunktacji, poziom_wydawcy|None)``. Nie dotyka rekordu —
    klasyfikacja z danych sesji (F2).
    """
    rok = session.normalized_data.get("year")

    # Patent nie ma źródła (zrodlo/wydawca) — brak podstawy do sugestii;
    # operator wpisuje punkty_kbn ręcznie.
    if session.rodzaj_rekordu == ImportSession.RodzajRekordu.PATENT:
        return (
            SugestiaPunktacji(
                None,
                rodzaj_braku=RodzajBraku.BRAK_DANYCH_ZRODLA,
                powod_braku="Patent nie ma źródła — brak sugestii punktacji.",
            ),
            None,
        )

    if not session.jest_wydawnictwem_zwartym:
        return zaproponuj_punkty_ciagle(session.zrodlo, rok), None

    wydawca = session.wydawca
    if wydawca is None:
        return (
            SugestiaPunktacji(
                None,
                rodzaj_braku=RodzajBraku.BRAK_WYDAWCY,
                powod_braku="Brak wydawcy — nie można zaproponować punktacji",
            ),
            None,
        )
    if not rok:
        return (
            SugestiaPunktacji(
                None,
                rodzaj_braku=RodzajBraku.BRAK_ROKU,
                powod_braku="Brak roku publikacji",
            ),
            None,
        )

    poziom = wydawca.get_tier(rok)
    cf = session.charakter_formalny
    matched = session.authors.exclude(matched_autor=None)
    sugestia = zaproponuj_punkty_zwarte(
        poziom=poziom,
        ksiazka=bool(cf and cf.charakter_sloty == const.CHARAKTER_SLOTY_KSIAZKA),
        rozdzial=bool(cf and cf.charakter_sloty == const.CHARAKTER_SLOTY_ROZDZIAL),
        autorstwo=matched.filter(typ_ogolny=const.TO_AUTOR).exists(),
        redakcja=matched.filter(typ_ogolny=const.TO_REDAKTOR).exists(),
    )
    return sugestia, poziom


def _punktacja_context(request, session, form=None):
    from bpp.models import Punktacja_Zrodla

    sugestia, poziom = _oblicz_sugestie(session)
    rok = session.normalized_data.get("year")

    punktacja_zrodla = None
    if not session.jest_wydawnictwem_zwartym and session.zrodlo and rok:
        punktacja_zrodla = Punktacja_Zrodla.objects.filter(
            zrodlo=session.zrodlo, rok=rok
        ).first()

    ostrzezenie_hst = any(
        a.matched_dyscyplina.dyscyplina_hst
        for a in session.authors.exclude(matched_dyscyplina=None)
    )

    if form is None:
        zapisane = session.matched_data.get("punkty_kbn")
        initial = {
            "punkty_kbn": zapisane if zapisane not in (None, "") else sugestia.punkty
        }
        form = PunktacjaForm(initial=initial)

    return {
        "session": session,
        "form": form,
        "sugestia": sugestia,
        "punktacja_zrodla": punktacja_zrodla,
        "poziom_wydawcy": poziom,
        "rok": rok,
        "ostrzezenie_hst": ostrzezenie_hst,
    }


def _render_punktacja_step(request, session, form=None):
    ctx = _punktacja_context(request, session, form)
    url = reverse("importer_publikacji:punktacja", kwargs={"session_id": session.pk})
    response = render(request, STEP_PUNKTACJA, ctx)
    response = _with_breadcrumbs_oob(response, request, session)
    return _push_url(response, url)


def _render_punktacja_full(request, session, form=None):
    ctx = _punktacja_context(request, session, form)
    return _render_full_page(request, STEP_PUNKTACJA, ctx)


# --- PBN check step -----------------------------------------------------------


def _pbn_context(request, session, *, do_search=True):
    """Zbuduj kontekst kroku „Sprawdź w PBN".

    Dla źródeł NIE-PBN sprawdza czy operator jest zalogowany do PBN i — jeśli
    tak — wyszukuje odpowiednik po DOI / tytule / stronie WWW. Zawsze pokazuje
    aktualnie wybrany odpowiednik (jeśli jest), niezależnie od wyszukiwania.
    """
    from urllib.parse import quote

    from .pbn_search import (
        _operator_pbn_logged_in,
        _pbn_url,
        _search_pbn_equivalents,
        _selected_pbn_publication,
    )

    logged_in = _operator_pbn_logged_in(request.user)
    selected = _selected_pbn_publication(session)
    selected_pbn_url = _pbn_url(session.uczelnia, selected.pk) if selected else None

    search = None
    if do_search and logged_in:
        search = _search_pbn_equivalents(session, request.user)
        # needs_auth w trakcie wyszukiwania = token nieważny po stronie PBN
        if search.get("needs_auth"):
            logged_in = False

    step_url = reverse("importer_publikacji:pbn", kwargs={"session_id": session.pk})
    authorize_url = f"{reverse('pbn_api:authorize')}?next={quote(step_url)}"

    return {
        "session": session,
        "logged_in": logged_in,
        "search": search,
        "selected": selected,
        "selected_pbn_url": selected_pbn_url,
        "authorize_url": authorize_url,
        "punktacja_url": reverse(
            "importer_publikacji:punktacja", kwargs={"session_id": session.pk}
        ),
        "review_url": reverse(
            "importer_publikacji:review", kwargs={"session_id": session.pk}
        ),
    }


def _render_pbn_step(request, session, *, do_search=True):
    """Renderuj partial kroku PBN z HX-Push-Url."""
    ctx = _pbn_context(request, session, do_search=do_search)
    url = reverse("importer_publikacji:pbn", kwargs={"session_id": session.pk})
    response = render(request, STEP_PBN, ctx)
    response = _with_breadcrumbs_oob(response, request, session)
    return _push_url(response, url)


def _render_pbn_full(request, session, *, do_search=True):
    """Renderuj pełną stronę z krokiem PBN."""
    ctx = _pbn_context(request, session, do_search=do_search)
    return _render_full_page(request, STEP_PBN, ctx)

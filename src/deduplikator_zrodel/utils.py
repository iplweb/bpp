import logging

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Count, Q

from bpp.models import Zrodlo
from import_common.normalization import (
    normalize_issn,
    normalize_skrot,
    normalize_tytul_zrodla,
)

from .models import IgnoredSource, NotADuplicate

logger = logging.getLogger(__name__)


def _norm(value, normalizer):
    """Znormalizowana wartość albo None, gdy `value` jest puste/None.

    Odwzorowuje wzorzec `normalizer(x) if x else None` rozsiany po module.
    """
    return normalizer(value) if value else None


def _both_equal(a, b):
    """True, gdy oba argumenty są prawdziwe (truthy) i równe."""
    return bool(a) and a == b


def _both_set_and_different(a, b):
    """True, gdy oba argumenty są ustawione (truthy) i różne."""
    return bool(a) and bool(b) and a != b


def _trigram_sim(field, value, pk):
    """Trigram similarity pola `field` względem `value` dla źródła `pk`.

    Zwraca None, gdy nie da się policzyć (brak rekordu / wynik None) —
    zachowuje stare `except (AttributeError, TypeError): pass`.
    """
    try:
        return (
            Zrodlo.objects.filter(pk=pk)
            .annotate(sim=TrigramSimilarity(field, value))
            .first()
            .sim
        )
    except (AttributeError, TypeError):
        return None


def _excluded_pair_ids(zrodlo):
    """ID źródeł oznaczonych z `zrodlo` jako NIE-duplikat (w obie strony),
    z pominięciem samego `zrodlo`."""
    pairs = NotADuplicate.objects.filter(
        Q(zrodlo=zrodlo) | Q(duplikat=zrodlo)
    ).values_list("duplikat_id", "zrodlo_id")

    excluded_ids = set()
    for dup_id, zr_id in pairs:
        excluded_ids.add(dup_id)
        excluded_ids.add(zr_id)
    excluded_ids.discard(zrodlo.pk)
    return excluded_ids


def _candidates_queryset(zrodlo):
    """QuerySet kandydatów na duplikaty: źródła z publikacjami, bez samego
    `zrodlo`, bez par NotADuplicate, bez IgnoredSource, bez innego MNiSW ID."""
    # Wyklucz źródła bez publikacji - sprawdzamy powiązane wydawnictwa ciągłe
    candidates = (
        Zrodlo.objects.exclude(pk=zrodlo.pk)
        .annotate(pub_count=Count("wydawnictwo_ciagle"))
        .filter(pub_count__gt=0)
    )

    # Wyklucz źródła już oznaczone jako "to nie duplikat"
    excluded_ids = _excluded_pair_ids(zrodlo)
    if excluded_ids:
        candidates = candidates.exclude(pk__in=excluded_ids)

    # Wyklucz źródła z listy ignorowanych
    ignored_ids = IgnoredSource.objects.values_list("zrodlo_id", flat=True)
    if ignored_ids:
        candidates = candidates.exclude(pk__in=ignored_ids)

    # Wyklucz źródła z INNYM MNiSW ID (jeśli główne źródło ma MNiSW ID)
    # Różne MNiSW ID = różne czasopisma ministerialne = NIE duplikaty
    if zrodlo.pbn_uid_id and zrodlo.pbn_uid.mniswId:
        candidates = candidates.exclude(
            Q(pbn_uid__mniswId__isnull=False)
            & ~Q(pbn_uid__mniswId=zrodlo.pbn_uid.mniswId)
        )

    return candidates


def _base_filters(zrodlo):
    """Q łączące kryteria: identyczny ISSN/E-ISSN, to samo pbn_uid, podobna
    nazwa (trigram >= 0.5)."""
    filters = Q()

    # 1. Identyczny ISSN lub E-ISSN (po normalizacji)
    norm_issn = _norm(zrodlo.issn, normalize_issn)
    norm_e_issn = _norm(zrodlo.e_issn, normalize_issn)
    if norm_issn:
        filters |= Q(issn__iregex=r"[\s\.\-]*".join(norm_issn))
    if norm_e_issn:
        filters |= Q(e_issn__iregex=r"[\s\.\-]*".join(norm_e_issn))

    # 2. To samo pbn_uid
    if zrodlo.pbn_uid_id:
        filters |= Q(pbn_uid_id=zrodlo.pbn_uid_id)

    # 3. Podobna nazwa (trigram similarity >= 0.5)
    if zrodlo.nazwa:
        norm_nazwa = normalize_tytul_zrodla(zrodlo.nazwa)
        similar_ids = (
            Zrodlo.objects
            # Prefiltr operatorem `%` (__trigram_similar) — używa indeksu GIN
            # trigram (bpp_zrodlo_nazwa_trgm), zamiast pełnego skanu tabeli.
            # Próg pg_trgm domyślnie 0.3 ≤ 0.5, więc to NADZBIÓR wyniku
            # `similarity >= 0.5`; dokładny próg dokłada filtr niżej —
            # wynik identyczny, ale liczony tylko na małym, przyciętym zbiorze.
            .filter(nazwa__trigram_similar=norm_nazwa)
            .annotate(similarity=TrigramSimilarity("nazwa", norm_nazwa))
            .filter(similarity__gte=0.5)
            .exclude(pk=zrodlo.pk)
            .values_list("pk", flat=True)
        )
        if similar_ids:
            filters |= Q(pk__in=similar_ids)

    return filters


def znajdz_podobne_zrodla(zrodlo):
    """
    Znajduje potencjalne duplikaty dla danego źródła.

    Returns:
        QuerySet of Zrodlo objects that might be duplicates
    """
    candidates = _candidates_queryset(zrodlo)
    filters = _base_filters(zrodlo)

    # 4. Podobny skrót — rozszerza filtry o już-pasujących kandydatów ze
    # zbliżonym skrótem (trigram >= 0.6, niższy próg).
    if zrodlo.skrot:
        norm_skrot = normalize_skrot(zrodlo.skrot)
        candidates_with_filters = candidates.filter(filters).annotate(
            skrot_similarity=TrigramSimilarity("skrot", norm_skrot)
        )
        similar_skrot_ids = candidates_with_filters.filter(
            skrot_similarity__gte=0.6
        ).values_list("pk", flat=True)
        if similar_skrot_ids:
            filters |= Q(pk__in=similar_skrot_ids)

    if not filters:
        return Zrodlo.objects.none()

    # select_related("pbn_uid") — orientacja pary (_canonical → _mnisw_rank)
    # czyta pbn_uid.mniswId/status każdego kandydata; bez tego N+1 w skanie.
    return candidates.filter(filters).distinct().select_related("pbn_uid")


def _score_nazwa(nazwa_glowna, norm_g, norm_k, kandydat_pk):
    """Punkty za nazwę: +60 za identyczną (case-insensitive po normalizacji),
    w przeciwnym razie +40 (trigram > 0.9) / +20 (trigram > 0.7) / 0."""
    if not (norm_g and norm_k):
        return 0
    if norm_g.lower() == norm_k.lower():
        return 60
    similarity = _trigram_sim("nazwa", nazwa_glowna, kandydat_pk)
    if similarity and similarity > 0.9:
        return 40
    if similarity and similarity > 0.7:
        return 20
    return 0


def _score_skrot(skrot_glowny, norm_g, norm_k, kandydat_pk):
    """Punkty za skrót (niska waga): +10 gdy trigram skrótu > 0.7, inaczej 0."""
    if not (norm_g and norm_k):
        return 0
    similarity = _trigram_sim("skrot", skrot_glowny, kandydat_pk)
    if similarity and similarity > 0.7:
        return 10
    return 0


def ocen_podobienstwo(zrodlo_glowne, zrodlo_kandydat):
    """
    Oblicza wskaźnik pewności, że dwa źródła to duplikaty.

    Returns:
        int: Punkty pewności (wyższe = większe prawdopodobieństwo duplikatu)
    """
    g, k = zrodlo_glowne, zrodlo_kandydat

    # 1. ISSN / E-ISSN: po +100 za zgodny numer, +20 bonus gdy oba zgodne.
    issn_match = _both_equal(
        _norm(g.issn, normalize_issn), _norm(k.issn, normalize_issn)
    )
    e_issn_match = _both_equal(
        _norm(g.e_issn, normalize_issn), _norm(k.e_issn, normalize_issn)
    )

    score = 100 * issn_match + 100 * e_issn_match
    if issn_match and e_issn_match:
        score += 20

    # 2. PBN UID matching: +80 za to samo pbn_uid.
    if _both_equal(g.pbn_uid_id, k.pbn_uid_id):
        score += 80

    # 3. Nazwa i 4. Skrót.
    score += _score_nazwa(
        g.nazwa,
        _norm(g.nazwa, normalize_tytul_zrodla),
        _norm(k.nazwa, normalize_tytul_zrodla),
        k.pk,
    )
    score += _score_skrot(
        g.skrot,
        _norm(g.skrot, normalize_skrot),
        _norm(k.skrot, normalize_skrot),
        k.pk,
    )

    # 5. Kary za różnice: różny rodzaj -15, różny zasięg -10.
    if _both_set_and_different(g.rodzaj_id, k.rodzaj_id):
        score -= 15
    if _both_set_and_different(g.zasieg_id, k.zasieg_id):
        score -= 10

    return score


def _get_site_domain(request=None):
    """Helper function to get site URL for XLSX export."""
    from bpp.util import site_url_for_request

    return site_url_for_request(request)


def _create_pbn_journal_url(pbn_uid):
    """Helper function to create PBN journal URL."""
    if pbn_uid:
        return f"https://pbn.nauka.gov.pl/-/journal/{pbn_uid}"
    return ""


def _format_worksheet_urls(ws, data_rows):
    """Format URLs as clickable hyperlinks in worksheet."""
    from openpyxl.styles import Font

    if len(data_rows) == 0:
        return

    url_columns = [
        3,
        7,
        10,
        14,
    ]  # C (BPP główne), G (PBN główne), J (BPP duplikat), N (PBN duplikat)

    for row_idx in range(2, len(data_rows) + 2):  # Start from row 2 (after header)
        for col_idx in url_columns:
            cell = ws.cell(row=row_idx, column=col_idx)  # Excel is 1-indexed
            if cell.value and str(cell.value).startswith("https://"):
                cell.hyperlink = cell.value
                cell.style = "Hyperlink"
                cell.font = Font(color="0000FF", underline="single")


def _candidate_zrodlo_row(zrodlo, fallback_nazwa, site_domain):
    """Wiersz danych źródła dla eksportu kandydata (na żywo z obiektu Zrodlo)."""
    nazwa = (zrodlo.nazwa if zrodlo else "") or fallback_nazwa or ""
    if not zrodlo:
        return [nazwa, "", "", "", "", "", ""]
    return [
        nazwa,
        zrodlo.pk,
        f"{site_domain}/bpp/browse/zrodla/{zrodlo.slug}/",
        zrodlo.issn or "",
        zrodlo.e_issn or "",
        zrodlo.pbn_uid_id or "",
        _create_pbn_journal_url(zrodlo.pbn_uid_id if zrodlo.pbn_uid_id else None),
    ]


def export_candidates_to_xlsx(candidates, request=None):
    """Eksportuje listę SourceDuplicateCandidate do XLSX.

    Kolumny odpowiadają staremu eksportowi (główne źródło + duplikat + score),
    ale źródłem danych są prekalkulowane pary ostatniego skanu, a nie liczenie
    w locie.
    """
    from io import BytesIO

    from openpyxl.workbook import Workbook

    from bpp.util import worksheet_columns_autosize, worksheet_create_table

    site_domain = _get_site_domain(request)

    data_rows = []
    for c in candidates:
        main_row = _candidate_zrodlo_row(c.main_zrodlo, c.main_nazwa, site_domain)
        dup_row = _candidate_zrodlo_row(
            c.duplicate_zrodlo, c.duplicate_nazwa, site_domain
        )
        data_rows.append([*main_row, *dup_row, c.confidence_score])

    data_rows.sort(key=lambda x: x[0])

    wb = Workbook()
    ws = wb.active
    ws.title = "Duplikaty źródeł"

    headers = [
        "Główne źródło",
        "BPP ID głównego źródła",
        "BPP URL głównego źródła",
        "ISSN głównego źródła",
        "E-ISSN głównego źródła",
        "PBN UID głównego źródła",
        "PBN URL głównego źródła",
        "Duplikat",
        "BPP ID duplikatu",
        "BPP URL duplikatu",
        "ISSN duplikatu",
        "E-ISSN duplikatu",
        "PBN UID duplikatu",
        "PBN URL duplikatu",
        "Pewność podobieństwa",
    ]
    ws.append(headers)
    for row in data_rows:
        ws.append(row)

    _format_worksheet_urls(ws, data_rows)
    worksheet_columns_autosize(ws)
    if data_rows:
        worksheet_create_table(ws)

    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()

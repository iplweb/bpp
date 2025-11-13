from cacheops import cached
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Count, Q

from bpp.models import Zrodlo
from import_common.normalization import (
    normalize_issn,
    normalize_skrot,
    normalize_tytul_zrodla,
)

from .models import IgnoredSource, NotADuplicate


def znajdz_podobne_zrodla(zrodlo):  # noqa: C901
    """
    Znajduje potencjalne duplikaty dla danego źródła.

    Returns:
        QuerySet of Zrodlo objects that might be duplicates
    """
    # Wyklucz źródła bez publikacji - sprawdzamy czy mają powiązane wydawnictwa ciągłe
    candidates = (
        Zrodlo.objects.exclude(pk=zrodlo.pk)
        .annotate(pub_count=Count("wydawnictwo_ciagle"))
        .filter(pub_count__gt=0)
    )

    # Wyklucz źródła już oznaczone jako "to nie duplikat"
    excluded_pks = NotADuplicate.objects.filter(
        Q(zrodlo=zrodlo) | Q(duplikat=zrodlo)
    ).values_list("duplikat_id", "zrodlo_id")

    excluded_ids = set()
    for dup_id, zr_id in excluded_pks:
        excluded_ids.add(dup_id)
        excluded_ids.add(zr_id)
    excluded_ids.discard(zrodlo.pk)

    if excluded_ids:
        candidates = candidates.exclude(pk__in=excluded_ids)

    # Wyklucz źródła z listy ignorowanych
    ignored_ids = IgnoredSource.objects.values_list("zrodlo_id", flat=True)
    if ignored_ids:
        candidates = candidates.exclude(pk__in=ignored_ids)

    # Wyklucz źródła z INNYM MNiSW ID (jeśli główne źródło ma MNiSW ID)
    # Różne MNiSW ID = różne czasopisma ministerialne = NIE duplikaty
    if zrodlo.pbn_uid_id and zrodlo.pbn_uid.mniswId:
        # Wyklucz źródła które mają mniswId RÓŻNY od głównego źródła
        candidates = candidates.exclude(
            Q(pbn_uid__mniswId__isnull=False)
            & ~Q(pbn_uid__mniswId=zrodlo.pbn_uid.mniswId)
        )

    # Kryteria wyszukiwania
    filters = Q()

    # 1. Identyczny ISSN lub E-ISSN (po normalizacji)
    norm_issn = normalize_issn(zrodlo.issn) if zrodlo.issn else None
    norm_e_issn = normalize_issn(zrodlo.e_issn) if zrodlo.e_issn else None

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
        similar_by_name = (
            Zrodlo.objects.annotate(similarity=TrigramSimilarity("nazwa", norm_nazwa))
            .filter(similarity__gte=0.5)
            .exclude(pk=zrodlo.pk)
        )
        similar_ids = similar_by_name.values_list("pk", flat=True)
        if similar_ids:
            filters |= Q(pk__in=similar_ids)

    # 4. Podobny skrót
    if zrodlo.skrot:
        norm_skrot = normalize_skrot(zrodlo.skrot)
        # Użyj trigram dla skrótów, ale z niższym progiem
        candidates_with_filters = candidates.filter(filters).annotate(
            skrot_similarity=TrigramSimilarity("skrot", norm_skrot)
        )
        # Dodaj te ze skrótem podobnym >= 0.6
        similar_skrot_ids = candidates_with_filters.filter(
            skrot_similarity__gte=0.6
        ).values_list("pk", flat=True)
        if similar_skrot_ids:
            filters |= Q(pk__in=similar_skrot_ids)

    if not filters:
        return Zrodlo.objects.none()

    return candidates.filter(filters).distinct()


def ocen_podobienstwo(zrodlo_glowne, zrodlo_kandydat):  # noqa: C901
    """
    Oblicza wskaźnik pewności, że dwa źródła to duplikaty.

    Returns:
        int: Punkty pewności (wyższe = większe prawdopodobieństwo duplikatu)
    """
    score = 0

    # Normalizacja danych
    norm_issn_g = normalize_issn(zrodlo_glowne.issn) if zrodlo_glowne.issn else None
    norm_issn_k = normalize_issn(zrodlo_kandydat.issn) if zrodlo_kandydat.issn else None

    norm_e_issn_g = (
        normalize_issn(zrodlo_glowne.e_issn) if zrodlo_glowne.e_issn else None
    )
    norm_e_issn_k = (
        normalize_issn(zrodlo_kandydat.e_issn) if zrodlo_kandydat.e_issn else None
    )

    norm_nazwa_g = (
        normalize_tytul_zrodla(zrodlo_glowne.nazwa) if zrodlo_glowne.nazwa else ""
    )
    norm_nazwa_k = (
        normalize_tytul_zrodla(zrodlo_kandydat.nazwa) if zrodlo_kandydat.nazwa else ""
    )

    norm_skrot_g = normalize_skrot(zrodlo_glowne.skrot) if zrodlo_glowne.skrot else ""
    norm_skrot_k = (
        normalize_skrot(zrodlo_kandydat.skrot) if zrodlo_kandydat.skrot else ""
    )

    # 1. ISSN matching
    issn_match = False
    e_issn_match = False

    if norm_issn_g and norm_issn_k and norm_issn_g == norm_issn_k:
        score += 100
        issn_match = True

    if norm_e_issn_g and norm_e_issn_k and norm_e_issn_g == norm_e_issn_k:
        score += 100
        e_issn_match = True

    # Bonus jeśli oba numery się zgadzają
    if issn_match and e_issn_match:
        score += 20

    # 2. PBN UID matching
    if (
        zrodlo_glowne.pbn_uid_id
        and zrodlo_kandydat.pbn_uid_id
        and zrodlo_glowne.pbn_uid_id == zrodlo_kandydat.pbn_uid_id
    ):
        score += 80

    # 3. Nazwa matching
    if norm_nazwa_g and norm_nazwa_k:
        if norm_nazwa_g.lower() == norm_nazwa_k.lower():
            score += 60
        else:
            # Oblicz trigram similarity dla nazwy
            try:
                similarity = (
                    Zrodlo.objects.filter(pk=zrodlo_kandydat.pk)
                    .annotate(sim=TrigramSimilarity("nazwa", zrodlo_glowne.nazwa))
                    .first()
                    .sim
                )
                if similarity and similarity > 0.9:
                    score += 40
                elif similarity and similarity > 0.7:
                    score += 20
            except (AttributeError, TypeError):
                pass

    # 4. Skrót matching (niska waga jak chciał użytkownik)
    if norm_skrot_g and norm_skrot_k:
        try:
            skrot_similarity = (
                Zrodlo.objects.filter(pk=zrodlo_kandydat.pk)
                .annotate(sim=TrigramSimilarity("skrot", zrodlo_glowne.skrot))
                .first()
                .sim
            )
            if skrot_similarity and skrot_similarity > 0.7:
                score += 10
        except (AttributeError, TypeError):
            pass

    # 5. Kary za różnice
    # Różny rodzaj źródła
    if (
        zrodlo_glowne.rodzaj_id
        and zrodlo_kandydat.rodzaj_id
        and zrodlo_glowne.rodzaj_id != zrodlo_kandydat.rodzaj_id
    ):
        score -= 15

    # Różny zasięg
    if (
        zrodlo_glowne.zasieg_id
        and zrodlo_kandydat.zasieg_id
        and zrodlo_glowne.zasieg_id != zrodlo_kandydat.zasieg_id
    ):
        score -= 10

    return score


@cached(timeout=10 * 60)
def analiza_duplikatow(zrodlo):
    """
    Znajduje i analizuje duplikaty dla danego źródła.

    Returns:
        list: Lista krotek (zrodlo_kandydat, score) posortowana po score malejąco
    """
    podobne = znajdz_podobne_zrodla(zrodlo)

    wyniki = []
    for kandydat in podobne:
        score = ocen_podobienstwo(zrodlo, kandydat)
        # Tylko źródła z dodatnią pewnością są pokazywane jako duplikaty
        if score > 0:
            wyniki.append((kandydat, score))

    # Sortuj po score malejąco
    wyniki.sort(key=lambda x: x[1], reverse=True)

    return wyniki


@cached(timeout=10 * 60)
def znajdz_pierwszego_zrodlo_z_duplikatami(excluded_ids=None):
    """
    Znajduje pierwsze źródło, które ma potencjalne duplikaty.

    Args:
        excluded_ids: Lista ID źródeł do pominięcia

    Returns:
        Zrodlo object lub None
    """
    if excluded_ids is None:
        excluded_ids = []

    # Wyklucz źródła z listy ignorowanych
    ignored_ids = list(IgnoredSource.objects.values_list("zrodlo_id", flat=True))
    all_excluded = list(set(excluded_ids + ignored_ids))

    # Znajdź źródła które potencjalnie mają duplikaty
    # Będziemy sprawdzać po kolei źródła z największą liczbą potencjalnych kandydatów

    # Filtr wykluczający źródła bez publikacji i bez ministerialnego ID
    # Musimy użyć annotate z Count dla wydawnictw ciągłych
    base_queryset = Zrodlo.objects.annotate(
        pub_count=Count("wydawnictwo_ciagle")
    ).filter(pub_count__gt=0, pbn_uid__mniswId__isnull=False)

    # Najpierw znajdź źródła z takim samym pbn_uid
    zrodla_z_pbn = (
        base_queryset.filter(pbn_uid_id__isnull=False)
        .exclude(pk__in=all_excluded)
        .values("pbn_uid_id")
        .annotate(cnt=Count("id"))
        .filter(cnt__gt=1)
        .order_by("-cnt")
    )

    if zrodla_z_pbn.exists():
        pbn_uid_id = zrodla_z_pbn.first()["pbn_uid_id"]
        zrodlo = (
            base_queryset.filter(pbn_uid_id=pbn_uid_id)
            .exclude(pk__in=all_excluded)
            .first()
        )
        if zrodlo:
            duplikaty = analiza_duplikatow(zrodlo)
            if duplikaty:
                return zrodlo

    # Następnie spróbuj z ISSN
    zrodla_z_issn = (
        base_queryset.filter(issn__isnull=False)
        .exclude(issn="")
        .exclude(pk__in=all_excluded)
        .order_by("issn")
    )

    for zrodlo in zrodla_z_issn[:100]:  # Sprawdź pierwsze 100
        duplikaty = analiza_duplikatow(zrodlo)
        if duplikaty:
            return zrodlo

    # Na końcu spróbuj po nazwie
    zrodla = base_queryset.exclude(pk__in=all_excluded).order_by("nazwa")

    for zrodlo in zrodla[:100]:  # Sprawdź pierwsze 100
        duplikaty = analiza_duplikatow(zrodlo)
        if duplikaty:
            return zrodlo

    return None


@cached(timeout=10 * 60)
def policz_zrodla_z_duplikatami():
    """
    Oblicza przybliżoną liczbę źródeł z potencjalnymi duplikatami.

    To jest szybka aproksymacja - nie sprawdza wszystkich źródeł.
    """
    # Policz źródła z tym samym pbn_uid
    count = (
        Zrodlo.objects.filter(pbn_uid_id__isnull=False)
        .values("pbn_uid_id")
        .annotate(cnt=Count("id"))
        .filter(cnt__gt=1)
        .count()
    )

    # To jest tylko przybliżenie - prawdziwa liczba może być inna
    return count


def _get_site_domain():
    """Helper function to get site domain for XLSX export."""
    from django.contrib.sites.models import Site

    try:
        current_site = Site.objects.get_current()
        return f"https://{current_site.domain}"
    except BaseException:
        return "https://bpp.iplweb.pl"


def _create_pbn_journal_url(pbn_uid):
    """Helper function to create PBN journal URL."""
    if pbn_uid:
        return f"https://pbn.nauka.gov.pl/-/journal/{pbn_uid}"
    return ""


def _prepare_source_data(zrodlo, site_domain):
    """Helper function to prepare source data for export."""
    return {
        "nazwa": zrodlo.nazwa or "",
        "bpp_id": zrodlo.pk,
        "bpp_url": f"{site_domain}/bpp/browse/zrodla/{zrodlo.slug}/",
        "issn": zrodlo.issn or "",
        "e_issn": zrodlo.e_issn or "",
        "pbn_uid": zrodlo.pbn_uid_id if zrodlo.pbn_uid_id else "",
        "pbn_url": _create_pbn_journal_url(
            zrodlo.pbn_uid_id if zrodlo.pbn_uid_id else None
        ),
    }


def _collect_duplicate_rows(base_queryset, processed_sources, site_domain):
    """Collect all duplicate rows for XLSX export."""
    data_rows = []

    zrodla_z_pbn = (
        base_queryset.filter(pbn_uid_id__isnull=False)
        .values("pbn_uid_id")
        .annotate(cnt=Count("id"))
        .filter(cnt__gt=1)
        .order_by("-cnt")
    )

    for pbn_group in zrodla_z_pbn:
        pbn_uid_id = pbn_group["pbn_uid_id"]
        sources_in_group = base_queryset.filter(pbn_uid_id=pbn_uid_id).order_by("nazwa")

        for zrodlo in sources_in_group:
            if zrodlo.pk in processed_sources:
                continue

            duplikaty = analiza_duplikatow(zrodlo)
            if not duplikaty:
                continue

            processed_sources.add(zrodlo.pk)
            glowne_data = _prepare_source_data(zrodlo, site_domain)
            duplicate_count = len(duplikaty)

            for kandydat, score in duplikaty:
                processed_sources.add(kandydat.pk)
                duplikat_data = _prepare_source_data(kandydat, site_domain)

                data_rows.append(
                    [
                        glowne_data["nazwa"],
                        glowne_data["bpp_id"],
                        glowne_data["bpp_url"],
                        glowne_data["issn"],
                        glowne_data["e_issn"],
                        glowne_data["pbn_uid"],
                        glowne_data["pbn_url"],
                        duplikat_data["nazwa"],
                        duplikat_data["bpp_id"],
                        duplikat_data["bpp_url"],
                        duplikat_data["issn"],
                        duplikat_data["e_issn"],
                        duplikat_data["pbn_uid"],
                        duplikat_data["pbn_url"],
                        score,
                        duplicate_count,
                    ]
                )

    return data_rows


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


def export_duplicates_to_xlsx():
    """
    Eksportuje wszystkie źródła z duplikatami do formatu XLSX.

    Struktura pliku XLSX:
    - Kolumna A: Główne źródło (nazwa)
    - Kolumna B: BPP ID głównego źródła
    - Kolumna C: BPP URL głównego źródła (kliknij link)
    - Kolumna D: ISSN głównego źródła
    - Kolumna E: E-ISSN głównego źródła
    - Kolumna F: PBN UID głównego źródła
    - Kolumna G: PBN URL głównego źródła (kliknij link)
    - Kolumna H: Duplikat (nazwa)
    - Kolumna I: BPP ID duplikatu
    - Kolumna J: BPP URL duplikatu (kliknij link)
    - Kolumna K: ISSN duplikatu
    - Kolumna L: E-ISSN duplikatu
    - Kolumna M: PBN UID duplikatu
    - Kolumna N: PBN URL duplikatu (kliknij link)
    - Kolumna O: Pewność podobieństwa (score)
    - Kolumna P: Ilość duplikatów

    Returns:
        bytes: Zawartość pliku XLSX
    """
    from io import BytesIO

    from openpyxl.workbook import Workbook

    from bpp.util import worksheet_columns_autosize, worksheet_create_table

    site_domain = _get_site_domain()

    # Pobierz źródła ignorowane
    ignored_ids = set(IgnoredSource.objects.values_list("zrodlo_id", flat=True))

    # Znajdź źródła które mają potencjalne duplikaty (z pbn_uid)
    base_queryset = (
        Zrodlo.objects.annotate(pub_count=Count("wydawnictwo_ciagle"))
        .filter(pub_count__gt=0, pbn_uid__mniswId__isnull=False)
        .exclude(pk__in=ignored_ids)
    )

    # Przygotuj dane do eksportu
    processed_sources = set()
    data_rows = _collect_duplicate_rows(base_queryset, processed_sources, site_domain)

    # Stwórz plik XLSX
    wb = Workbook()
    ws = wb.active
    ws.title = "Duplikaty źródeł"

    # Sortuj dane alfabetycznie po głównym źródle
    data_rows.sort(key=lambda x: x[0])

    # Nagłówki
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
        "Ilość duplikatów",
    ]

    ws.append(headers)

    # Dodaj dane
    for row in data_rows:
        ws.append(row)

    # Sformatuj URL-e jako klikalne linki
    _format_worksheet_urls(ws, data_rows)

    # Sformatuj arkusz
    worksheet_columns_autosize(ws)
    if len(data_rows) > 0:
        worksheet_create_table(ws)

    # Zapisz do BytesIO
    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()

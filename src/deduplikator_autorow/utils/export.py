"""
Funkcje eksportu duplikatów do plików.
"""

from collections import Counter
from io import BytesIO

from django.contrib.sites.models import Site
from openpyxl.styles import Font
from openpyxl.workbook import Workbook

from bpp.util import worksheet_columns_autosize, worksheet_create_table
from deduplikator_autorow.models import DuplicateCandidate


def _get_site_domain():
    """Pobierz domenę serwisu do konstrukcji pełnych URLi."""
    try:
        current_site = Site.objects.get_current()
        return f"https://{current_site.domain}"
    except BaseException:
        return "https://bpp.iplweb.pl"


def _create_pbn_url(autor):
    """Zwraca aktualny URL do profilu autora w PBN.

    Używa Autor.link_do_pbn() które łączy LINK_PBN_DO_AUTORA z pbn_api_root
    z konfiguracji Uczelni - dotychczas zaszyty hardcoded https://pbn.nauka.gov.pl/
    sedno-webapp/persons/details/{uid} prowadził do martwego/pustego endpointu.
    """
    if not autor or not autor.pbn_uid_id:
        return ""
    url = autor.link_do_pbn()
    return url or ""


def _get_author_name(candidate_name, autor):
    """Pobierz nazwę autora z cache'a lub z modelu."""
    if candidate_name:
        return candidate_name
    return f"{autor.nazwisko or ''} {autor.imiona or ''}".strip()


def _build_candidate_row(candidate, site_domain, duplicate_counts):
    """Buduje pojedynczy wiersz danych dla kandydata na duplikat."""
    main = candidate.main_autor
    dup = candidate.duplicate_autor

    main_name = _get_author_name(candidate.main_autor_name, main)
    dup_name = _get_author_name(candidate.duplicate_autor_name, dup)

    return [
        main_name,
        main.orcid or "",
        main.pk,
        f"{site_domain}/bpp/autor/{main.pk}/",
        main.pbn_uid_id or "",
        _create_pbn_url(main),
        dup_name,
        dup.orcid or "",
        dup.pk,
        f"{site_domain}/bpp/autor/{dup.pk}/",
        dup.pbn_uid_id or "",
        _create_pbn_url(dup),
        round(candidate.confidence_percent, 2),
        duplicate_counts[candidate.main_autor_id],
        "PBN" if candidate.scan_mode == "pbn" else "Ogólny",
    ]


def _format_url_hyperlinks(ws, data_rows_count):
    """Formatuje kolumny URL jako klikalne linki."""
    # Kolumny z URL-ami (1-indexed):
    #   D = BPP URL głównego autora
    #   F = PBN URL głównego autora
    #   J = BPP URL duplikatu
    #   L = PBN URL duplikatu
    url_columns = [4, 6, 10, 12]

    for row_idx in range(2, data_rows_count + 2):  # Start from row 2 (after header)
        for col_idx in url_columns:
            cell = ws.cell(row=row_idx, column=col_idx)
            if cell.value and str(cell.value).startswith("https://"):
                cell.hyperlink = cell.value
                cell.style = "Hyperlink"
                cell.font = Font(color="0000FF", underline="single")


def export_duplicates_to_xlsx():
    """
    Eksportuje kandydatów na duplikaty do formatu XLSX.

    Korzysta z pre-calculated danych z tabeli DuplicateCandidate
    (wypełnianej podczas skanowania) zamiast przeliczać wszystko od nowa.

    Struktura pliku XLSX:
    - Kolumna A: Główny autor (NAZWISKO IMIĘ)
    - Kolumna B: ORCID głównego autora
    - Kolumna C: BPP ID głównego autora
    - Kolumna D: BPP URL głównego autora (kliknij link)
    - Kolumna E: PBN UID głównego autora
    - Kolumna F: PBN URL głównego autora (kliknij link)
    - Kolumna G: Duplikat (NAZWISKO IMIĘ)
    - Kolumna H: ORCID duplikatu
    - Kolumna I: BPP ID duplikatu
    - Kolumna J: BPP URL duplikatu (kliknij link)
    - Kolumna K: PBN UID duplikatu
    - Kolumna L: PBN URL duplikatu (kliknij link)
    - Kolumna M: Pewność podobieństwa (0.0-1.0)
    - Kolumna N: Ilość duplikatów
    - Kolumna O: Tryb (PBN / Ogólny)

    Returns:
        bytes: Zawartość pliku XLSX
    """
    site_domain = _get_site_domain()

    # JEDNO zapytanie zamiast tysięcy! Materializujemy raz, żeby Counter
    # i list-comprehension nie wykonywały dwóch iteracji po queryset
    # (każda iteracja = ponowny SQL).
    candidates = list(
        DuplicateCandidate.objects.filter(status=DuplicateCandidate.Status.PENDING)
        .select_related(
            "main_autor",
            "duplicate_autor",
        )
        .order_by("main_autor_name", "-confidence_score")
    )

    # Policz duplikaty per główny autor (dla kolumny "Ilość duplikatów")
    duplicate_counts = Counter(c.main_autor_id for c in candidates)

    data_rows = [
        _build_candidate_row(candidate, site_domain, duplicate_counts)
        for candidate in candidates
    ]

    # Stwórz plik XLSX
    wb = Workbook()
    ws = wb.active
    ws.title = "Duplikaty autorów"

    # Nagłówki
    headers = [
        "Główny autor",
        "ORCID głównego autora",
        "BPP ID głównego autora",
        "BPP URL głównego autora",
        "PBN UID głównego autora",
        "PBN URL głównego autora",
        "Duplikat",
        "ORCID duplikatu",
        "BPP ID duplikatu",
        "BPP URL duplikatu",
        "PBN UID duplikatu",
        "PBN URL duplikatu",
        "Pewność podobieństwa",
        "Ilość duplikatów",
        "Tryb",
    ]

    ws.append(headers)

    # Dodaj dane
    for row in data_rows:
        ws.append(row)

    # Sformatuj URL-e jako klikalne linki
    if data_rows:
        _format_url_hyperlinks(ws, len(data_rows))

    # Sformatuj arkusz
    worksheet_columns_autosize(ws)
    if data_rows:
        worksheet_create_table(ws)

    # Zapisz do BytesIO
    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()

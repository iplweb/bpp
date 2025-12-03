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


def _create_pbn_url(pbn_uid):
    """Tworzy URL do profilu autora w PBN."""
    if pbn_uid:
        return f"https://pbn.nauka.gov.pl/sedno-webapp/persons/details/{pbn_uid}"
    return ""


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
        main.pk,
        f"{site_domain}/bpp/autor/{main.pk}/",
        main.pbn_uid_id or "",
        _create_pbn_url(main.pbn_uid_id),
        dup_name,
        dup.pk,
        f"{site_domain}/bpp/autor/{dup.pk}/",
        dup.pbn_uid_id or "",
        _create_pbn_url(dup.pbn_uid_id),
        round(candidate.confidence_percent, 2),
        duplicate_counts[candidate.main_autor_id],
    ]


def _format_url_hyperlinks(ws, data_rows_count):
    """Formatuje kolumny URL jako klikalne linki."""
    # Kolumny z URL-ami: C (BPP główny), E (PBN główny), H (BPP duplikat), J (PBN duplikat)
    url_columns = [3, 5, 8, 10]  # 1-indexed dla Excel

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
    - Kolumna B: BPP ID głównego autora
    - Kolumna C: BPP URL głównego autora (kliknij link)
    - Kolumna D: PBN UID głównego autora
    - Kolumna E: PBN URL głównego autora (kliknij link)
    - Kolumna F: Duplikat (NAZWISKO IMIĘ)
    - Kolumna G: BPP ID duplikatu
    - Kolumna H: BPP URL duplikatu (kliknij link)
    - Kolumna I: PBN UID duplikatu
    - Kolumna J: PBN URL duplikatu (kliknij link)
    - Kolumna K: Pewność podobieństwa (0.0-1.0)
    - Kolumna L: Ilość duplikatów

    Returns:
        bytes: Zawartość pliku XLSX
    """
    site_domain = _get_site_domain()

    # JEDNO zapytanie zamiast tysięcy!
    # Pobierz wszystkich kandydatów ze statusem PENDING
    candidates = (
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
        "BPP ID głównego autora",
        "BPP URL głównego autora",
        "PBN UID głównego autora",
        "PBN URL głównego autora",
        "Duplikat",
        "BPP ID duplikatu",
        "BPP URL duplikatu",
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

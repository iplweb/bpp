"""
Funkcje eksportu duplikatów do plików.
"""

from io import BytesIO

from django.contrib.sites.models import Site
from openpyxl.styles import Font
from openpyxl.workbook import Workbook

from bpp.util import worksheet_columns_autosize, worksheet_create_table
from deduplikator_autorow.models import NotADuplicate
from pbn_api.models import Scientist

from .analysis import analiza_duplikatow


def export_duplicates_to_xlsx():  # noqa: C901
    """
    Eksportuje wszystkich autorów z duplikatami do formatu XLSX.

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
    # Pobierz domenę serwisu do konstrukcji pełnych URLi
    try:
        current_site = Site.objects.get_current()
        site_domain = f"https://{current_site.domain}"
    except BaseException:
        # Fallback jeśli Site nie jest skonfigurowany
        site_domain = "https://bpp.iplweb.pl"

    def create_pbn_url(pbn_uid):
        """Helper function to create PBN author URL"""
        if pbn_uid:
            return f"https://pbn.nauka.gov.pl/sedno-webapp/persons/details/{pbn_uid}"
        return ""

    # Pobierz wszystkich autorów z duplikatami
    # Najpierw pobierz IDs autorów oznaczonych jako nie-duplikat
    excluded_author_ids = list(NotADuplicate.objects.values_list("autor", flat=True))

    # Następnie znajdź Scientists, którzy mają związanych autorów BPP z duplikatami
    scientists_with_authors = Scientist.objects.filter(
        osobazinstytucji__isnull=False,
        autor__isnull=False,  # Scientist musi mieć związanego autora BPP
    ).exclude(autor__in=excluded_author_ids)

    # Przygotuj dane do eksportu
    data_rows = []
    processed_scientists = set()

    for scientist in scientists_with_authors:
        if scientist.pk in processed_scientists:
            continue

        try:
            # Pobierz analizę duplikatów
            analiza_result = analiza_duplikatow(scientist.osobazinstytucji)

            if "error" in analiza_result or not analiza_result.get("analiza"):
                continue

            glowny_autor = analiza_result["glowny_autor"]
            duplikaty = analiza_result["analiza"]

            if not duplikaty:
                continue

            # Dodaj głównego autora do przetworzonych
            processed_scientists.add(scientist.pk)

            # Przygotuj dane głównego autora
            # Format: NAZWISKO IMIĘ
            glowny_autor_name = (
                f"{glowny_autor.nazwisko or ''} {glowny_autor.imiona or ''}".strip()
            )
            glowny_bpp_id = glowny_autor.pk
            glowny_bpp_url = f"{site_domain}/bpp/autor/{glowny_autor.pk}/"
            glowny_pbn_uid = glowny_autor.pbn_uid_id if glowny_autor.pbn_uid_id else ""
            glowny_pbn_url = create_pbn_url(glowny_pbn_uid)

            # Liczba duplikatów dla tego autora
            duplicate_count = len(duplikaty)

            # Dodaj każdy duplikat jako osobny wiersz
            for duplikat_info in duplikaty:
                autor_duplikat = duplikat_info["autor"]
                pewnosc = duplikat_info["pewnosc"]

                # Oznacz duplikat jako przetworzony
                if hasattr(autor_duplikat, "pbn_uid") and autor_duplikat.pbn_uid:
                    processed_scientists.add(autor_duplikat.pbn_uid.pk)

                # Przygotuj dane duplikatu
                # Format: NAZWISKO IMIĘ
                duplikat_name = (
                    f"{autor_duplikat.nazwisko or ''} "
                    f"{autor_duplikat.imiona or ''}".strip()
                )
                duplikat_bpp_id = autor_duplikat.pk
                duplikat_bpp_url = f"{site_domain}/bpp/autor/{autor_duplikat.pk}/"
                duplikat_pbn_uid = (
                    autor_duplikat.pbn_uid_id if autor_duplikat.pbn_uid_id else ""
                )
                duplikat_pbn_url = create_pbn_url(duplikat_pbn_uid)

                data_rows.append(
                    [
                        glowny_autor_name,
                        glowny_bpp_id,
                        glowny_bpp_url,
                        glowny_pbn_uid,
                        glowny_pbn_url,
                        duplikat_name,
                        duplikat_bpp_id,
                        duplikat_bpp_url,
                        duplikat_pbn_uid,
                        duplikat_pbn_url,
                        round(pewnosc / 100, 2),  # Convert percentage to decimal
                        duplicate_count,  # Number of duplicates for this main author
                    ]
                )

        except Exception:
            # Pomiń autorów z błędami w analizie
            continue

    # Stwórz plik XLSX
    wb = Workbook()
    ws = wb.active
    ws.title = "Duplikaty autorów"

    # Sortuj dane alfabetycznie po głównym autorze
    data_rows.sort(key=lambda x: x[0])  # Sort by main author name

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
    if len(data_rows) > 0:
        # Kolumny z URL-ami: C (BPP główny), E (PBN główny), H (BPP duplikat), J (PBN duplikat)
        url_columns = [3, 5, 8, 10]  # 0-indexed: C=2, E=4, H=7, J=9

        for row_idx in range(2, len(data_rows) + 2):  # Start from row 2 (after header)
            for col_idx in url_columns:
                cell = ws.cell(row=row_idx, column=col_idx)  # Excel is 1-indexed
                if cell.value and str(cell.value).startswith("https://"):
                    # Make it a hyperlink
                    cell.hyperlink = cell.value
                    cell.style = "Hyperlink"
                    cell.font = Font(color="0000FF", underline="single")

    # Sformatuj arkusz
    worksheet_columns_autosize(ws)
    if len(data_rows) > 0:
        worksheet_create_table(ws)

    # Zapisz do BytesIO
    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()

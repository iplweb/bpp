from django.db.models import Exists, OuterRef, Q
from openpyxl import Workbook

from django.utils import timezone

from bpp.models import Wydawnictwo_Ciagle, Zrodlo


def get_issns_from_last_5_years():
    """
    Pobiera wszystkie unikatowe ISSN i e-ISSN czasopism które miały publikacje w ostatnich 5 latach.

    Returns:
        list: Posortowana lista unikalnych ISSN
    """
    # Oblicz datę 5 lat wstecz
    five_years_ago = timezone.now().year - 5

    # Pobierz źródła (czasopisma) które mają publikacje w ostatnich 5 latach
    zrodla_with_publications = Zrodlo.objects.filter(
        Exists(
            Wydawnictwo_Ciagle.objects.filter(
                zrodlo=OuterRef("pk"), rok__gte=five_years_ago
            )
        )
    )

    # Pobierz wszystkie unikatowe ISSN (wykluczając puste wartości)
    issns = (
        zrodla_with_publications.filter(Q(issn__isnull=False) & ~Q(issn=""))
        .values_list("issn", flat=True)
        .distinct()
        .order_by("issn")
    )

    # Pobierz wszystkie unikatowe e-ISSN (wykluczając puste wartości)
    e_issns = (
        zrodla_with_publications.filter(Q(e_issn__isnull=False) & ~Q(e_issn=""))
        .values_list("e_issn", flat=True)
        .distinct()
        .order_by("e_issn")
    )

    # Połącz wszystkie ISSN i usuń duplikaty
    all_issns = sorted(set(list(issns) + list(e_issns)))

    return all_issns


def generate_issn_xlsx_workbook(issns):
    """
    Generuje workbook z ISSN pogrupowanymi po 600 elementów w kolumnie.

    Args:
        issns (list): Lista ISSN do umieszczenia w pliku

    Returns:
        openpyxl.Workbook: Workbook z danymi ISSN
    """
    # Stwórz workbook i worksheet
    wb = Workbook()
    ws = wb.active
    ws.title = "ISSN Czasopism"

    # Grupuj ISSN po 600 w kolumnie
    col = 1
    row = 1

    for i, issn in enumerate(issns):
        # Jeśli przekroczono 600 wierszy, przejdź do następnej kolumny
        if i > 0 and i % 600 == 0:
            col += 1
            row = 1

        ws.cell(row=row, column=col, value=issn)
        row += 1

    return wb


def generate_issn_xlsx():
    """
    Generuje workbook z ISSN czasopism które miały publikacje w ostatnich 5 latach,
    pogrupowanymi po 600 elementów w kolumnie.

    Returns:
        openpyxl.Workbook: Workbook z danymi ISSN
    """
    issns = get_issns_from_last_5_years()
    return generate_issn_xlsx_workbook(issns)

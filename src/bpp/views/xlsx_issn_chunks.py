from django.http import HttpResponse

from django.utils import timezone

from bpp.export.issn import generate_issn_xlsx


def xlsx_issn_chunks(request):
    """
    Widok Django generujący plik XLSX z ISSN czasopism pogrupowanymi po 600 elementów w kolumnie.
    Pobiera czasopisma które miały publikacje w ostatnich 5 latach.
    """
    # Generuj workbook z danymi ISSN
    wb = generate_issn_xlsx()

    # Przygotuj odpowiedź HTTP
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = (
        f'attachment; filename="issn_czasopism_{timezone.now().strftime("%Y%m%d")}.xlsx"'
    )

    # Zapisz workbook do response
    wb.save(response)

    return response

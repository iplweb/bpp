from braces.views import GroupRequiredMixin
from django.http import HttpResponse
from django.views import View

from django.utils import timezone

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.export.issn import generate_issn_xlsx


class XlsxIssnChunksView(GroupRequiredMixin, View):
    """
    Widok Django generujący plik XLSX z ISSN czasopism pogrupowanymi po 600 elementów w kolumnie.
    Pobiera czasopisma które miały publikacje w ostatnich 5 latach.
    Dostępny tylko dla zalogowanych użytkowników z grupą "wprowadzanie danych".
    """

    group_required = GR_WPROWADZANIE_DANYCH

    def get(self, request):
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


# Backward compatibility
xlsx_issn_chunks = XlsxIssnChunksView.as_view()

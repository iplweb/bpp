"""Export-related views.

``download_duplicates_xlsx`` returns the full duplicates list as an XLSX
attachment for offline review.
"""

import datetime
import sys

import rollbar
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect

from bpp.const import GR_WPROWADZANIE_DANYCH

from ..utils import export_duplicates_to_xlsx
from .helpers import group_required


@group_required(GR_WPROWADZANIE_DANYCH)
def download_duplicates_xlsx(request):
    """
    Widok do pobierania listy duplikatów w formacie XLSX.

    Generuje plik XLSX ze wszystkimi autorami z duplikatami,
    zawierający głównego autora, jego PBN UID, duplikat i jego PBN UID.
    """
    try:
        # Generuj plik XLSX
        xlsx_content = export_duplicates_to_xlsx(request)

        # Stwórz odpowiedź HTTP z plikiem
        response = HttpResponse(
            xlsx_content,
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )

        # Nazwa pliku z datą
        filename = (
            f"duplikaty_autorow_{datetime.date.today().strftime('%Y-%m-%d')}.xlsx"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        rollbar.report_exc_info(sys.exc_info())
        messages.error(request, f"Błąd podczas generowania pliku XLSX: {str(e)}")
        return redirect("deduplikator_autorow:duplicate_authors")

"""Odesłanie do deduplikatora źródeł.

Gdy import (CrossRef admin prefill lub kreator importera publikacji) nie
dopasuje źródła, bo w bazie istnieją zduplikowane rekordy o tej samej
nazwie/skrócie i różnych ISSN-ach, pokazujemy użytkownikowi komunikat z
linkiem do deduplikatora źródeł, zamiast po cichu zostawić puste pole
(FD#422).
"""

from django.contrib import messages
from django.urls import reverse
from django.utils.html import format_html

from crossref_bpp.core import Komparator


def ostrzez_o_zduplikowanych_zrodlach(request, wynik):
    """Jeśli duplikaty zablokowały dopasowanie źródła — odeślij do deduplikatora.

    Działa tylko gdy ``wynik.zduplikowane_zrodla`` jest niepuste (grupa źródeł
    o tej samej nazwie/skrócie i sprzecznych ISSN-ach), czyli dokładnie wtedy,
    gdy duplikaty uniemożliwiły jednoznaczne dopasowanie i pole źródła zostaje
    puste.
    """
    if request is None or wynik is None:
        return
    zduplikowane = getattr(wynik, "zduplikowane_zrodla", None)
    if not zduplikowane:
        return

    nazwy = ", ".join(
        sorted({(z.nazwa or z.skrot or "").strip() for z in zduplikowane})
    )
    url = reverse("deduplikator_zrodel:duplicate_sources")
    messages.warning(
        request,
        format_html(
            "Nie dopasowano automatycznie źródła, bo w bazie istnieją "
            "zduplikowane źródła o tej samej nazwie ({}) i różnych ISSN-ach. "
            'Rozwiąż duplikaty w <a href="{}">deduplikatorze źródeł</a>, '
            "a następnie ponów dopasowanie.",
            nazwy,
            url,
        ),
    )


def ostrzez_o_zduplikowanych_zrodlach_crossref(request, z):
    """Wariant przyjmujący surowy słownik CrossRef API (admin prefill)."""
    try:
        tytul_kontenera = z.get("container-title")[0]
    except (IndexError, TypeError):
        # IndexError: pusta lista; TypeError: brak klucza (None nie indeksujemy).
        return
    if not tytul_kontenera:
        return
    ostrzez_o_zduplikowanych_zrodlach(
        request, Komparator.porownaj_container_title(tytul_kontenera)
    )

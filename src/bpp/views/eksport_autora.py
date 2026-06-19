"""
Publiczne widoki eksportu wszystkich publikacji autora do formatów
bibliograficznych (§3.3).

Dwa endpointy zwracają plik do pobrania:

- ``/bpp/autor/<pk>/eksport.bib`` → BibTeX
- ``/bpp/autor/<pk>/eksport.ris`` → RIS

Obie strony są PUBLICZNE (bez logowania) — dane bibliograficzne i tak są
widoczne na publicznej stronie autora.
"""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views import View

from bpp.export.bibtex import export_to_bibtex
from bpp.export.ris import export_to_ris
from bpp.models import Autor, Rekord

#: Maksymalna liczba eksportowanych rekordów. Zabezpiecza przed OOM przy
#: autorach z gigantyczną liczbą prac (eksport materializuje instancje
#: konkretnych modeli, więc jest N+1 — twardy limit jest tańszy niż ryzyko).
MAKS_EKSPORT = 5000


class _BazaEksportuAutoraView(View):
    """
    Wspólna baza obu eksportów. Podklasy różnią się tylko formaterem,
    typem zawartości i rozszerzeniem pliku.
    """

    #: Funkcja ``(publications) -> str`` produkująca treść pliku.
    formatter = None
    #: Wartość nagłówka ``Content-Type``.
    content_type = None
    #: Rozszerzenie pliku (bez kropki), np. ``"bib"``.
    extension = None

    def naglowek_obciecia(self, wyeksportowano: int, wszystkich: int) -> str:
        """
        Zwraca prefiks dołączany do treści gdy nastąpiło obcięcie do
        ``MAKS_EKSPORT``. Domyślnie pusty — RIS (format liniowy) nie ma
        wygodnego sposobu na komentarz, więc tam polegamy wyłącznie na
        samym limicie. BibTeX nadpisuje to komentarzem ``% ...``.
        """
        return ""

    def get(self, request, pk):
        autor = get_object_or_404(Autor, pk=pk)

        qs = Rekord.objects.prace_autora(autor)
        wszystkich = qs.count()
        oryginaly = [r.original for r in qs[:MAKS_EKSPORT]]

        tekst = self.formatter(oryginaly)

        if wszystkich > MAKS_EKSPORT:
            prefiks = self.naglowek_obciecia(len(oryginaly), wszystkich)
            if prefiks:
                tekst = prefiks + tekst

        resp = HttpResponse(tekst, content_type=self.content_type)
        nazwa = autor.slug or f"autor-{autor.pk}"
        resp["Content-Disposition"] = f'attachment; filename="{nazwa}.{self.extension}"'
        return resp


class AutorEksportBibtexView(_BazaEksportuAutoraView):
    formatter = staticmethod(export_to_bibtex)
    content_type = "application/x-bibtex; charset=utf-8"
    extension = "bib"

    def naglowek_obciecia(self, wyeksportowano: int, wszystkich: int) -> str:
        return (
            f"% Wyeksportowano pierwsze {wyeksportowano} z {wszystkich} prac "
            f"(limit {MAKS_EKSPORT}).\n\n"
        )


class AutorEksportRisView(_BazaEksportuAutoraView):
    formatter = staticmethod(export_to_ris)
    content_type = "application/x-research-info-systems; charset=utf-8"
    extension = "ris"
    # RIS jest formatem czysto liniowym (każda linia = tag rekordu), więc nie
    # ma czystego miejsca na komentarz o obcięciu jak `% ...` w BibTeX-ie.
    # Świadomie pomijamy notkę i polegamy na samym limicie MAKS_EKSPORT.

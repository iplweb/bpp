"""
Publiczne widoki eksportu wszystkich publikacji autora do formatów
bibliograficznych (§3.3).

Dwa endpointy zwracają plik do pobrania:

- ``/bpp/autor/<pk>/eksport.bib`` → BibTeX
- ``/bpp/autor/<pk>/eksport.ris`` → RIS

Obie strony są PUBLICZNE (bez logowania) — dane bibliograficzne i tak są
widoczne na publicznej stronie autora.
"""

from datetime import timedelta

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django_sendfile import sendfile

from bpp.export.bibtex import export_to_bibtex
from bpp.export.ris import export_to_ris
from bpp.models import Autor, AutorEksportTask, Rekord

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


#: Okno deduplikacji: kolejne żądania startu tego samego eksportu (autor +
#: format) w ciągu tylu minut reużywają istniejącego zadania zamiast kolejkować
#: nowe. Chroni przed spamowaniem Celery przez anonimowych użytkowników.
DEDUPE_MINUTES = 5


class StartEksportAutoraView(View):
    """Uruchom asynchroniczne zadanie eksportu (publiczny, anonimowy).

    Deduplikuje: jeśli istnieje świeże (ostatnie ``DEDUPE_MINUTES`` minut)
    zadanie dla tego samego autora i formatu w stanie innym niż ``failed``,
    reużywa je zamiast kolejkować nowe — zapobiega spamowaniu Celery.
    """

    def get(self, request, pk, format):
        from bpp.tasks import generuj_eksport_autora

        autor = get_object_or_404(Autor, pk=pk)

        od = timezone.now() - timedelta(minutes=DEDUPE_MINUTES)
        istniejacy = (
            AutorEksportTask.objects.filter(
                autor=autor,
                format=format,
                created_at__gte=od,
            )
            .exclude(status="failed")
            .order_by("-created_at")
            .first()
        )
        if istniejacy is not None:
            return redirect("bpp:autor_eksport_status", pk=istniejacy.pk)

        task = AutorEksportTask.objects.create(autor=autor, format=format)
        generuj_eksport_autora.delay(str(task.pk))
        return redirect("bpp:autor_eksport_status", pk=task.pk)


class EksportAutoraStatusView(View):
    """Strona statusu / partial HTMX (publiczny). Autoryzacja przez UUID."""

    def get(self, request, pk):
        task = get_object_or_404(AutorEksportTask, pk=pk)
        context = {"task": task}

        if request.headers.get("HX-Request"):
            return render(request, "browse/eksport_autora/_progress.html", context)
        return render(request, "browse/eksport_autora/task_status.html", context)


class EksportAutoraDownloadView(View):
    """Pobranie gotowego pliku (publiczny). Autoryzacja przez UUID + status."""

    def get(self, request, pk):
        task = get_object_or_404(AutorEksportTask, pk=pk, status="completed")
        if not task.result_file:
            raise Http404("Plik nie został odnaleziony.")

        return sendfile(
            request,
            task.result_file.path,
            attachment=True,
            attachment_filename=task.nazwa_pliku,
            mimetype=task.content_type,
        )

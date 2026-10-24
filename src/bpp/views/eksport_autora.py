"""
Publiczne widoki eksportu wszystkich publikacji autora do formatów
bibliograficznych (§3.3).

Dwa endpointy zwracają plik do pobrania:

- ``/bpp/autor/<pk>/eksport.bib`` → BibTeX
- ``/bpp/autor/<pk>/eksport.ris`` → RIS

Oba generują plik SYNCHRONICZNIE w wątku requestu (do ``MAKS_EKSPORT`` prac,
N+1), więc są tylko dla ZALOGOWANYCH — anonimowy bot mógłby nimi zająć
workery. Publiczna ścieżka to eksport asynchroniczny (``StartEksportAutoraView``)
z ALTCHA dla anonimów.
"""

from datetime import timedelta

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django_altcha import AltchaField
from django_sendfile import sendfile

from bpp.export.bibtex import export_to_bibtex
from bpp.export.ris import export_to_ris
from bpp.models import Autor, AutorEksportTask, Rekord
from bpp.permissions import moze_wprowadzac_dane
from bpp.util.ukryte_statusy import ukryte_statusy_eksportu

#: Maksymalna liczba eksportowanych rekordów. Zabezpiecza przed OOM przy
#: autorach z gigantyczną liczbą prac (eksport materializuje instancje
#: konkretnych modeli, więc jest N+1 — twardy limit jest tańszy niż ryzyko).
MAKS_EKSPORT = 5000

#: Limit synchronicznych eksportów na użytkownika w oknie ``OKNO_LIMITU_S``
#: sekund. Nie dotyczy osób z uprawnieniami redakcyjnymi.
LIMIT_EKSPORTOW_SYNC = 10
OKNO_LIMITU_S = 60


def _autor_dla_eksportu(request, pk):
    """Autor do eksportu; ukryci (``pokazuj=False``) tylko dla redakcji."""
    autor = get_object_or_404(Autor, pk=pk)
    if not autor.pokazuj and not moze_wprowadzac_dane(request.user):
        raise Http404
    return autor


def _przekroczono_limit(request) -> bool:
    if moze_wprowadzac_dane(request.user):
        return False
    key = f"eksport-autora-sync:{request.user.pk}"
    # ``add`` inicjuje licznik tylko gdy klucza nie ma; ``incr`` jest atomowy.
    cache.add(key, 0, timeout=OKNO_LIMITU_S)
    try:
        licznik = cache.incr(key)
    except ValueError:
        # DummyCache (domyślny w dev/test) nic nie przechowuje — ``incr``
        # zgłasza brak klucza; traktujemy to jak pierwsze wywołanie.
        licznik = 1
    return licznik > LIMIT_EKSPORTOW_SYNC


class _BazaEksportuAutoraView(LoginRequiredMixin, View):
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
        autor = _autor_dla_eksportu(request, pk)

        if _przekroczono_limit(request):
            return HttpResponse(
                "Zbyt wiele żądań eksportu. Spróbuj ponownie za chwilę.",
                status=429,
                content_type="text/plain; charset=utf-8",
            )

        qs = Rekord.objects.prace_autora(autor)
        # Plik wychodzi poza stronę — reguła publiczna także dla redakcji.
        ukryte = ukryte_statusy_eksportu(request)
        if ukryte:
            qs = qs.exclude(status_korekty_id__in=ukryte)
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


class StartEksportuForm(forms.Form):
    """Formularz startu eksportu. Dla anonima dokłada pole ALTCHA."""

    def __init__(self, *args, captcha_wymagany=False, **kwargs):
        super().__init__(*args, **kwargs)
        if captcha_wymagany:
            # `auto="onload"`: na tę stronę wchodzi się po to, żeby wygenerować
            # eksport, więc PoW liczymy od razu — przycisk działa bez czekania.
            self.fields["captcha"] = AltchaField(
                label="Weryfikacja",
                challengeurl=reverse_lazy("bpp:autor_eksport_altcha"),
                auto="onload",
            )


class StartEksportAutoraView(View):
    """Uruchom asynchroniczne zadanie eksportu (publiczny).

    GET pokazuje stronę z przyciskiem „Generuj” i NIC nie kolejkuje —
    crawler idący po linkach nie uruchomi zadań. Zadanie startuje POST,
    a anonim musi przejść ALTCHA (proof-of-work), żeby boty nie zapchały
    Celery. Zalogowany startuje bez captchy.

    Deduplikuje: jeśli istnieje świeże (ostatnie ``DEDUPE_MINUTES`` minut)
    zadanie dla tego samego autora i formatu w stanie innym niż ``failed``,
    reużywa je zamiast kolejkować nowe.
    """

    template_name = "browse/eksport_autora/start.html"

    def _form(self, request, data=None):
        return StartEksportuForm(
            data, captcha_wymagany=not request.user.is_authenticated
        )

    def _render(self, request, autor, format, form):
        return render(
            request,
            self.template_name,
            {
                "autor": autor,
                "nazwa_formatu": dict(AutorEksportTask.FORMAT_CHOICES)[format],
                "form": form,
            },
        )

    def get(self, request, pk, format):
        autor = _autor_dla_eksportu(request, pk)
        return self._render(request, autor, format, self._form(request))

    def post(self, request, pk, format):
        from bpp.tasks import generuj_eksport_autora

        autor = _autor_dla_eksportu(request, pk)
        form = self._form(request, request.POST)
        if not form.is_valid():
            return self._render(request, autor, format, form)

        # Zakres widoczności (ukryte statusy) zapisujemy w zadaniu — worker
        # Celery nie ma requestu. Plik jest publiczny po UUID, więc zakres
        # jest publiczny także dla redakcji; wchodzi do deduplikacji, żeby
        # zadania różnych uczelni (inne ukryte statusy) nie były współdzielone.
        ukryte = ukryte_statusy_eksportu(request)

        od = timezone.now() - timedelta(minutes=DEDUPE_MINUTES)
        istniejacy = (
            AutorEksportTask.objects.filter(
                autor=autor,
                format=format,
                created_at__gte=od,
                ukryte_statusy=ukryte,
            )
            .exclude(status="failed")
            .order_by("-created_at")
            .first()
        )
        if istniejacy is not None:
            return redirect("bpp:autor_eksport_status", pk=istniejacy.pk)

        task = AutorEksportTask.objects.create(
            autor=autor, format=format, ukryte_statusy=ukryte
        )
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

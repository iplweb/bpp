"""
Eksport wszystkich publikacji autora do formatów bibliograficznych (§3.3).

Plik generuje WYŁĄCZNIE zadanie Celery (``generuj_eksport_autora``) —
synchroniczne generowanie w wątku requestu przy dużym dorobku potrafiło
zająć worker serwera WWW. Ścieżka:

- ``StartEksportAutoraView`` — strona z przyciskiem „Generuj” (POST
  kolejkuje zadanie; anonim przechodzi ALTCHA),
- ``EksportAutoraStatusView`` — postęp,
- ``EksportAutoraDownloadView`` — pobranie gotowego pliku.

Redakcja (``moze_wprowadzac_dane``) dostaje pełny dorobek (bez wykluczania
ukrytych statusów korekty); takie zadanie jest oznaczone
``tylko_dla_redakcji`` i jego status/plik widzi wyłącznie redakcja.

Dawne adresy ``/bpp/autor/<pk>/eksport.bib`` i ``.ris`` przekierowują na
stronę startu eksportu w odpowiednim formacie.
"""

import logging
from datetime import timedelta

from django import forms
from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django_altcha import AltchaField
from django_sendfile import sendfile

from bpp.models import Autor, AutorEksportTask
from bpp.permissions import moze_wprowadzac_dane
from bpp.util.ukryte_statusy import ukryte_statusy_eksportu, widoczni_autorzy
from django_bpp.client_ip import get_client_ip

logger = logging.getLogger(__name__)

#: Limit NOWYCH zadań eksportu zlecanych przez zalogowanego użytkownika bez
#: uprawnień redakcyjnych w oknie ``OKNO_LIMITU_S`` sekund. Anonima chroni
#: ALTCHA (proof-of-work) oraz limity per IP i kolejki (niżej), redakcji
#: limit nie dotyczy.
LIMIT_STARTOW_EKSPORTU = 10
OKNO_LIMITU_S = 60


def _autor_dla_eksportu(request, pk):
    """Autor do eksportu; ukryci (``pokazuj=False``) tylko dla redakcji."""
    return get_object_or_404(widoczni_autorzy(Autor.objects.all(), request), pk=pk)


def _przekroczono_limit(request) -> bool:
    """Czy zalogowany (nie-redaktor) przekroczył limit startów eksportu."""
    if not request.user.is_authenticated or moze_wprowadzac_dane(request.user):
        return False
    key = f"eksport-autora-start:{request.user.pk}"
    # ``add`` inicjuje licznik tylko gdy klucza nie ma; ``incr`` jest atomowy.
    cache.add(key, 0, timeout=OKNO_LIMITU_S)
    try:
        licznik = cache.incr(key)
    except ValueError:
        # DummyCache (domyślny w dev/test) nic nie przechowuje — ``incr``
        # zgłasza brak klucza; traktujemy to jak pierwsze wywołanie.
        licznik = 1
    return licznik > LIMIT_STARTOW_EKSPORTU


#: Okno limitu startów eksportu przez anonima z jednego IP (sekundy).
OKNO_LIMITU_ANON_IP_S = 60 * 60

#: Zadania anonimowe starsze niż tyle minut nie liczą się do limitu kolejki,
#: nawet gdy wiszą w stanie ``pending``/``running`` (np. po restarcie
#: workera Celery) — inaczej jedno zawieszenie blokowałoby anonimów na stałe.
ODCIECIE_WISZACYCH_ANON_MINUTES = 60

KOMUNIKAT_LIMIT_ANON_IP = (
    "Z tego adresu wykorzystano już godzinny limit eksportów dla osób "
    "niezalogowanych. Spróbuj ponownie za godzinę albo zaloguj się — "
    "zalogowani użytkownicy mają wyższy limit."
)
KOMUNIKAT_LIMIT_ANON_KOLEJKA = (
    "Obecnie trwa zbyt wiele eksportów zleconych przez osoby niezalogowane. "
    "Spróbuj ponownie za kilka minut albo zaloguj się — zalogowanych ten "
    "limit nie dotyczy."
)

#: Klucz ``pg_advisory_xact_lock`` serializujący sprawdzenie limitu kolejki
#: anonimowej z utworzeniem zadania (stała, dowolna liczba 64-bit).
_ADVISORY_LOCK_KOLEJKA_ANON = 0x6270705F65616B71


def _zarezerwuj_start_anon_ip(request) -> bool:
    """Atomowo policz start eksportu anonima z IP klienta.

    Zwraca ``False``, gdy przekroczono
    ``settings.EKSPORT_AUTORA_LIMIT_ANON_IP_NA_GODZINE`` (0 = brak limitu).
    Wzór licznika jak w ``zglos_publikacje.limity``: ``cache.add`` zakłada
    klucz z TTL (okno stałe od pierwszego startu), ``cache.incr`` jest
    atomowy. Cache bez liczników (DummyCache) — start przepuszczany.
    """
    limit = getattr(settings, "EKSPORT_AUTORA_LIMIT_ANON_IP_NA_GODZINE", 0) or 0
    if limit <= 0:
        return True
    ip = get_client_ip(request) or "brak-ip"
    klucz = f"eksport-autora-start:ip:{ip}"
    for _proba in range(2):
        cache.add(klucz, 0, timeout=OKNO_LIMITU_ANON_IP_S)
        try:
            return cache.incr(klucz) <= limit
        except ValueError:
            # Klucz wygasł między add a incr (albo cache bez liczników) —
            # jedna ponowna próba z nowym oknem.
            continue
    logger.warning(
        "eksport autora: cache nie obsługuje liczników — limit startów "
        "anonima per IP nieaktywny dla tego żądania"
    )
    return True


def _kolejka_anon_pelna() -> bool:
    """Czy liczba anonimowych zadań w toku osiągnęła limit kolejki.

    Liczone są zadania ``zlecone_anonimowo`` w stanie ``pending``/``running``
    utworzone w ostatnich ``ODCIECIE_WISZACYCH_ANON_MINUTES`` minutach.
    """
    limit = getattr(settings, "EKSPORT_AUTORA_LIMIT_ANON_W_KOLEJCE", 0) or 0
    if limit <= 0:
        return False
    od = timezone.now() - timedelta(minutes=ODCIECIE_WISZACYCH_ANON_MINUTES)
    w_toku = AutorEksportTask.objects.filter(
        zlecone_anonimowo=True,
        status__in=("pending", "running"),
        created_at__gte=od,
    ).count()
    return w_toku >= limit


def _zadanie_dostepne(request, task) -> bool:
    """Zadanie redakcji (pełny dorobek) widzi tylko redakcja."""
    return not task.tylko_dla_redakcji or moze_wprowadzac_dane(request.user)


class PrzekierowanieEksportuAutoraView(View):
    """Dawne ``eksport.bib``/``eksport.ris`` → strona startu eksportu w tle."""

    #: Format eksportu (``bib`` / ``ris``), ustawiany w ``urls.py``.
    format = None

    def get(self, request, pk):
        return redirect("bpp:autor_eksport_start", pk=pk, format=self.format)


#: Okno deduplikacji: kolejne żądania startu tego samego eksportu (autor,
#: format, zakres widoczności) w ciągu tylu minut reużywają istniejącego zadania zamiast kolejkować
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
    zadanie dla tego samego autora, formatu i zakresu widoczności w stanie
    innym niż ``failed``, reużywa je zamiast kolejkować nowe. Zalogowany
    użytkownik bez uprawnień redakcyjnych ma limit nowych zadań
    (``LIMIT_STARTOW_EKSPORTU`` na ``OKNO_LIMITU_S`` s). Anonim ma limit
    nowych zadań na IP (``EKSPORT_AUTORA_LIMIT_ANON_IP_NA_GODZINE``) i
    globalny limit anonimowych zadań w toku
    (``EKSPORT_AUTORA_LIMIT_ANON_W_KOLEJCE``).
    """

    template_name = "browse/eksport_autora/start.html"

    def _form(self, request, data=None):
        return StartEksportuForm(
            data, captcha_wymagany=not request.user.is_authenticated
        )

    def _render(
        self, request, autor, format, form, status=200, zachec_do_logowania=False
    ):
        return render(
            request,
            self.template_name,
            {
                "autor": autor,
                "nazwa_formatu": dict(AutorEksportTask.FORMAT_CHOICES)[format],
                "form": form,
                "zachec_do_logowania": zachec_do_logowania,
            },
            status=status,
        )

    def _odmowa(self, request, autor, format, form, komunikat, status):
        # Błąd jako non-field error nad przyciskiem; widget ALTCHA dostaje
        # nowe wyzwanie, więc kolejna próba wymaga ponownej weryfikacji.
        form.add_error(None, komunikat)
        return self._render(
            request,
            autor,
            format,
            form,
            status=status,
            zachec_do_logowania=not request.user.is_authenticated,
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

        # Zakres widoczności zapisujemy w zadaniu — worker Celery nie ma
        # requestu. Redakcja dostaje pełny dorobek w zadaniu oznaczonym
        # ``tylko_dla_redakcji`` (status/plik widzi wyłącznie redakcja);
        # pozostali — zakres publiczny (fail-closed). Oba pola wchodzą do
        # deduplikacji: zadanie redakcji nigdy nie trafia do kogoś spoza niej
        # i odwrotnie, a zadania uczelni o innych ukrytych statusach nie są
        # współdzielone.
        tylko_dla_redakcji = moze_wprowadzac_dane(request.user)
        ukryte = [] if tylko_dla_redakcji else ukryte_statusy_eksportu(request)

        od = timezone.now() - timedelta(minutes=DEDUPE_MINUTES)
        istniejacy = (
            AutorEksportTask.objects.filter(
                autor=autor,
                format=format,
                created_at__gte=od,
                ukryte_statusy=ukryte,
                tylko_dla_redakcji=tylko_dla_redakcji,
            )
            .exclude(status="failed")
            .order_by("-created_at")
            .first()
        )
        if istniejacy is not None:
            return redirect("bpp:autor_eksport_status", pk=istniejacy.pk)

        if _przekroczono_limit(request):
            return HttpResponse(
                "Zbyt wiele żądań eksportu. Spróbuj ponownie za chwilę.",
                status=429,
                content_type="text/plain; charset=utf-8",
            )

        anonim = not request.user.is_authenticated
        if anonim:
            task, odmowa = self._utworz_zadanie_anonima(
                request, autor, format, form, ukryte
            )
            if odmowa is not None:
                return odmowa
        else:
            task = AutorEksportTask.objects.create(
                autor=autor,
                format=format,
                ukryte_statusy=ukryte,
                tylko_dla_redakcji=tylko_dla_redakcji,
            )
        generuj_eksport_autora.delay(str(task.pk))
        return redirect("bpp:autor_eksport_status", pk=task.pk)

    def _utworz_zadanie_anonima(self, request, autor, format, form, ukryte):
        """Utwórz zadanie anonima po sprawdzeniu limitów.

        Zwraca ``(zadanie, None)`` albo — przy przekroczonym limicie —
        ``(None, odpowiedź HTTP z komunikatem)``.

        Limit kolejki sprawdzamy pod ``pg_advisory_xact_lock`` w jednej
        transakcji z ``create`` — równoległe starty anonimów nie przekroczą
        limitu. Limit kolejki idzie przed limitem IP, żeby odmowa z powodu
        pełnej kolejki nie zużywała puli startów danego IP.
        """
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(%s)",
                    [_ADVISORY_LOCK_KOLEJKA_ANON],
                )
            if _kolejka_anon_pelna():
                return None, self._odmowa(
                    request, autor, format, form, KOMUNIKAT_LIMIT_ANON_KOLEJKA, 503
                )
            if not _zarezerwuj_start_anon_ip(request):
                return None, self._odmowa(
                    request, autor, format, form, KOMUNIKAT_LIMIT_ANON_IP, 429
                )
            zadanie = AutorEksportTask.objects.create(
                autor=autor,
                format=format,
                ukryte_statusy=ukryte,
                tylko_dla_redakcji=False,
                zlecone_anonimowo=True,
            )
        return zadanie, None


class EksportAutoraStatusView(View):
    """Strona statusu / partial HTMX. Autoryzacja przez UUID; zadanie
    ``tylko_dla_redakcji`` — dodatkowo tylko dla redakcji (inaczej 404)."""

    def get(self, request, pk):
        task = get_object_or_404(AutorEksportTask, pk=pk)
        if not _zadanie_dostepne(request, task):
            raise Http404
        context = {"task": task}

        if request.headers.get("HX-Request"):
            return render(request, "browse/eksport_autora/_progress.html", context)
        return render(request, "browse/eksport_autora/task_status.html", context)


class EksportAutoraDownloadView(View):
    """Pobranie gotowego pliku. Autoryzacja przez UUID + status; zadanie
    ``tylko_dla_redakcji`` — dodatkowo tylko dla redakcji (inaczej 404)."""

    def get(self, request, pk):
        task = get_object_or_404(AutorEksportTask, pk=pk, status="completed")
        if not _zadanie_dostepne(request, task):
            raise Http404
        if not task.result_file:
            raise Http404("Plik nie został odnaleziony.")

        return sendfile(
            request,
            task.result_file.path,
            attachment=True,
            attachment_filename=task.nazwa_pliku,
            mimetype=task.content_type,
        )

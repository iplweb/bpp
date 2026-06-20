"""Self-service picker wyróżnionych publikacji autora (Faza 2, §3.4).

Zalogowany autor zarządza listą WŁASNYCH wyróżnionych prac na swojej
podstronie: dodaje, usuwa i zmienia kolejność. Persystencja do istniejącego
modelu ``WybranaPublikacjaAutora``.

Bezpieczeństwo jest tu krytyczne i egzekwowane SERWEROWO na każdej akcji:

* ``WymagajAutoraMixin`` gatuje dostęp (anonim → login, brak ``user.autor`` →
  „Mój profil"), więc każdy widok operuje na ``request.user.autor``;
* DODANIE waliduje, że wskazany ``Rekord`` faktycznie należy do dorobku autora
  (``Rekord.objects.prace_autora(autor)``) — autor nie może wyróżnić cudzej
  pracy;
* USUNIĘCIE/PRZESUNIĘCIE filtruje wiersze przez ``autor=request.user.autor`` —
  cudze ``WybranaPublikacjaAutora`` są niewidoczne i nietykalne;
* duplikat (``unique_together``) jest przyjaznym no-op, nie 500.
"""

from dal_select2.widgets import ListSelect2
from django import forms
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from django.http import Http404, JsonResponse
from django.utils.html import strip_tags
from django.views.generic import TemplateView, View

from bpp.models import Rekord
from bpp.models.wybrana_publikacja import WybranaPublikacjaAutora
from bpp.views.profil_edycja import WymagajAutoraMixin

# Limit podpowiedzi w autouzupełnianiu — autor może mieć setki prac.
LIMIT_AUTOCOMPLETE = 20


class DodajWyrozionaForm(forms.Form):
    """Pole „dodaj" pickera — Select2 (DAL ``ListSelect2``), spójne z resztą
    serwisu (ten sam widget i theme co inne autouzupełnienia, np. nawigacja).

    ``Rekord`` ma złożony klucz (``TupleField``), więc nie da się tu użyć
    ``ModelSelect2`` (zakłada pojedynczy pk) — ``ListSelect2`` operuje na
    dowolnych parach ``(id, tekst)``, gdzie ``id`` = „<ct>-<obj>". Po wyborze
    JS woła akcję ``dodaj`` i czyści pole (wartość nie jest walidowana przez
    formularz — własność sprawdza serwer w akcji)."""

    praca = forms.CharField(
        required=False,
        label="",
        widget=ListSelect2(
            url="bpp:profil-wybrane-publikacje-autocomplete",
            attrs={
                "data-placeholder": "Zacznij wpisywać tytuł swojej pracy…",
                "data-minimum-input-length": 2,
                "data-dropdown-css-class": "wpa-dropdown",
            },
        ),
    )


def _wiersze_wybrane(autor):
    """Wybrane publikacje autora z dołączonym obiektem publikacji (GFK)."""
    wiersze = list(
        autor.wybrane_publikacje.select_related("content_type").order_by("kolejnosc")
    )
    return [w for w in wiersze if w.publikacja is not None]


def _opis_rekordu(rekord):
    """Czytelny opis pracy do podpowiedzi (opis bibliograficzny > tytuł).

    Zwraca CZYSTY TEKST — opis bibliograficzny zawiera HTML (``<b>``/``<i>``),
    a podpowiedzi w JS wstawiamy przez ``textContent`` (bezpiecznie, bez
    ryzyka DOM-XSS), więc surowe tagi byłyby widoczne dosłownie. ``strip_tags``
    daje spójny, czytelny tekst zarówno tu, jak i na liście (szablon: filtr
    ``striptags``).
    """
    return strip_tags(
        rekord.opis_bibliograficzny_cache or rekord.tytul_oryginalny
    ).strip()


class ProfilWybranePublikacjeView(WymagajAutoraMixin, TemplateView):
    """Strona zarządzania wyróżnionymi publikacjami (lista + dodawanie)."""

    template_name = "bpp/profil_wybrane_publikacje.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["wybrane"] = _wiersze_wybrane(self.request.user.autor)
        context["form_dodaj"] = DodajWyrozionaForm()
        return context


class ProfilWybranePublikacjeAutocompleteView(WymagajAutoraMixin, View):
    """Autouzupełnianie WŁASNYCH prac autora (źródło dla „dodaj").

    Format zgodny z DAL/Select2: ``{"results": [{"id": "<ct>-<obj>",
    "text": ...}], "pagination": {"more": false}}`` (zasila ``ListSelect2``).
    Pyta wyłącznie ``Rekord.objects.prace_autora(request.user.autor)`` — autor
    nie zobaczy tu (a tym samym nie wyróżni) cudzej pracy.
    """

    def get(self, request, *args, **kwargs):
        autor = request.user.autor
        q = (request.GET.get("q") or "").strip()
        qs = Rekord.objects.prace_autora(autor)
        if q:
            qs = qs.filter(tytul_oryginalny__icontains=q)
        qs = qs.order_by("-rok", "tytul_oryginalny_sort")[:LIMIT_AUTOCOMPLETE]
        results = [
            {
                "id": f"{rekord.pk[0]}-{rekord.pk[1]}",
                "text": _opis_rekordu(rekord),
            }
            for rekord in qs
        ]
        return JsonResponse({"results": results, "pagination": {"more": False}})


class ProfilWybranePublikacjeAkcjaView(WymagajAutoraMixin, View):
    """Akcje AJAX: ``dodaj`` / ``usun`` / ``przesun`` — JSON in/out.

    Wszystkie operują na ``request.user.autor.wybrane_publikacje``. Każda akcja
    waliduje własność serwerowo (patrz docstring modułu).
    """

    def post(self, request, *args, **kwargs):
        autor = request.user.autor
        akcja = request.POST.get("akcja")
        if akcja == "dodaj":
            return self._dodaj(request, autor)
        if akcja == "usun":
            return self._usun(request, autor)
        if akcja == "przesun":
            return self._przesun(request, autor)
        return JsonResponse({"ok": False, "blad": "Nieznana akcja."}, status=400)

    def _parsuj_identyfikator(self, surowy):
        """``"<ct>-<obj>"`` → ``(ct_id, obj_id)`` lub ``None`` przy błędzie."""
        try:
            ct_str, obj_str = (surowy or "").split("-", 1)
            return int(ct_str), int(obj_str)
        except (ValueError, AttributeError):
            return None

    def _dodaj(self, request, autor):
        rozbite = self._parsuj_identyfikator(request.POST.get("rekord"))
        if rozbite is None:
            return JsonResponse(
                {"ok": False, "blad": "Nieprawidłowy identyfikator."}, status=400
            )
        ct_id, obj_id = rozbite

        # KLUCZOWA walidacja własności: praca MUSI należeć do dorobku autora.
        nalezy = Rekord.objects.prace_autora(autor).filter(pk=[ct_id, obj_id]).exists()
        if not nalezy:
            return JsonResponse(
                {"ok": False, "blad": "To nie jest Twoja publikacja."}, status=400
            )

        nastepna = autor.wybrane_publikacje.count()
        try:
            wpa = WybranaPublikacjaAutora.objects.create(
                autor=autor,
                content_type=ContentType.objects.get_for_id(ct_id),
                object_id=obj_id,
                kolejnosc=nastepna,
            )
        except IntegrityError:
            # unique_together(autor, content_type, object_id) — duplikat to
            # przyjazny no-op, nie błąd serwera.
            return JsonResponse(
                {"ok": True, "duplikat": True, "info": "Praca jest już wyróżniona."}
            )
        return JsonResponse({"ok": True, "pk": wpa.pk})

    def _usun(self, request, autor):
        try:
            pk = int(request.POST.get("pk"))
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "blad": "Brak wiersza."}, status=400)
        # Filtr po ``autor`` zapewnia, że cudzy wiersz jest nie do ruszenia.
        wpa = autor.wybrane_publikacje.filter(pk=pk).first()
        if wpa is None:
            raise Http404("Brak takiego wiersza wśród Twoich wyróżnionych prac.")
        wpa.delete()
        return JsonResponse({"ok": True})

    def _przesun(self, request, autor):
        """Ustaw kolejność 0..n-1 wg listy PK; cudze/nieznane PK są pomijane."""
        kolejnosc_pk = request.POST.getlist("kolejnosc")
        # Operujemy WYŁĄCZNIE na własnych wierszach — cudze PK z payloadu są
        # niewidoczne dla tego querysetu, więc nie zostaną dotknięte.
        wlasne = {w.pk: w for w in autor.wybrane_publikacje.all()}
        nowa = 0
        for surowy in kolejnosc_pk:
            try:
                pk = int(surowy)
            except (TypeError, ValueError):
                continue
            wpa = wlasne.get(pk)
            if wpa is None:
                continue
            if wpa.kolejnosc != nowa:
                wpa.kolejnosc = nowa
                wpa.save(update_fields=["kolejnosc"])
            nowa += 1
        return JsonResponse({"ok": True})

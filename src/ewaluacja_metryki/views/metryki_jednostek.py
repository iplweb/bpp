"""Metryki jednostek i wydziałów — zestawienia PDF (FD#617)."""

import ssl
import unicodedata

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django.views.generic import TemplateView, View

from bpp.models import Jednostka
from django_bpp.version import VERSION
from ewaluacja_common.okres import okres_dla_request
from raport_slotow.uczelnia_helper import uczelnia_dla_odczytu

from ..dostep_jednostek import (
    jednostki_do_wgladu,
    ma_dostep_do_metryk_jednostek,
    moze_ogladac_metryki_jednostki,
)
from ..metryki_jednostek import zbuduj_metryki_jednostki, zbuduj_metryki_wydzialu
from ..models import MetrykaAutora
from ..uczelnia_scope import scope_metryki

# Inter (OFL, podzbiór z pełną polską łacinką — static/ewaluacja_metryki/fonty).
# Pliki czytamy z dysku (file://), a nie przez HTTP: WeasyPrint nie musi wtedy
# dociągać hashowanych statyków serwisu (por. FD#405). Jeden plik na grubość:
# kroju strony (Open Sans) nie da się użyć, bo jest pocięty na zakresy znaków,
# a WeasyPrint gubi wtedy polskie litery. Brak pliku = powrót do DejaVu Sans.
# Podgląd w przeglądarce bierze te same pliki zwykłym adresem statyków.
GRUBOSCI_FONTU = {400: "Regular", 600: "SemiBold", 700: "Bold"}


def deklaracje_fontow(przegladarka=False):
    css = []
    for waga, nazwa in GRUBOSCI_FONTU.items():
        plik = f"ewaluacja_metryki/fonty/Inter-{nazwa}.otf"
        sciezka = finders.find(plik)
        if not sciezka:
            continue
        url = staticfiles_storage.url(plik) if przegladarka else f"file://{sciezka}"
        css.append(
            "@font-face { font-family: 'Inter'; font-style: normal; "
            f"font-weight: {waga}; src: url('{url}'); }}"
        )
    return mark_safe("\n".join(css))


def uzywa_wydzialow(request) -> bool:
    """Czy uczelnia ma strukturę uczelnia → wydział → jednostka (ustawienie
    „Używaj wydziałów”). Tylko wtedy pokazujemy „Metryki wydziałów”."""
    uczelnia = uczelnia_dla_odczytu(request)
    return bool(uczelnia is not None and uczelnia.uzywaj_wydzialow)


def jednostki_z_metrykami(request):
    """Jednostki widoczne dla użytkownika, które mają metryki w wybranym
    okresie — z liczbą autorów i sumą punktów (lista wyboru, profil).

    Jednostki obce (``skupia_pracownikow=False``) pomijamy — to nie są
    jednostki uczelni, raport metryk nie ma dla nich sensu."""
    qs = scope_metryki(
        MetrykaAutora.objects.filter(
            jednostka__isnull=False, jednostka__skupia_pracownikow=True
        ),
        uczelnia_dla_odczytu(request),
        okres_dla_request(request),
    )
    dozwolone = jednostki_do_wgladu(request.user)
    if dozwolone is not None:
        qs = qs.filter(jednostka__in=dozwolone)
    return (
        qs.values(
            "jednostka_id",
            "jednostka__nazwa",
            "jednostka__skrot",
            "jednostka__wydzial__nazwa",
        )
        .annotate(
            liczba_autorow=Count("autor", distinct=True),
            punkty=Sum("punkty_nazbierane"),
        )
        .order_by("jednostka__nazwa")
    )


# Polskie litery, których NFD nie rozkłada na literę + znak diakrytyczny.
_BEZ_DIAKRYTYKOW = str.maketrans({"ł": "l", "Ł": "l"})


def do_wyszukiwania(tekst):
    """Tekst do porównań w wyszukiwarce: małe litery, bez polskich znaków
    („Łódź” → „lodz”). Ta sama normalizacja jest w skrypcie listy."""
    tekst = (tekst or "").translate(_BEZ_DIAKRYTYKOW).lower()
    return "".join(
        z for z in unicodedata.normalize("NFD", tekst) if not unicodedata.combining(z)
    )


def tekst_wyszukiwania_jednostki(wiersz):
    return do_wyszukiwania(
        " ".join(
            filter(
                None,
                (
                    wiersz.get("jednostka__nazwa"),
                    wiersz.get("jednostka__skrot"),
                    wiersz.get("jednostka__wydzial__nazwa"),
                ),
            )
        )
    )


def filtruj_jednostki(wiersze, fraza):
    """Wiersze, których nazwa/skrót/wydział zawierają WSZYSTKIE słowa frazy
    (kolejność dowolna, bez polskich znaków i wielkości liter)."""
    slowa = do_wyszukiwania(fraza).split()
    if not slowa:
        return list(wiersze)
    return [
        w
        for w in wiersze
        if all(slowo in tekst_wyszukiwania_jednostki(w) for slowo in slowa)
    ]


def wydzialy_z_metrykami(request):
    """Wydziały (korzenie drzew jednostek) widoczne dla użytkownika, które
    mają metryki w wybranym okresie — z liczbą autorów, jednostek i punktów.
    Jednostki obce (``skupia_pracownikow=False``) pomijamy."""
    qs = scope_metryki(
        MetrykaAutora.objects.filter(
            jednostka__isnull=False, jednostka__skupia_pracownikow=True
        ),
        uczelnia_dla_odczytu(request),
        okres_dla_request(request),
    )
    sumy = {
        w["jednostka__tree_id"]: w
        for w in qs.values("jednostka__tree_id").annotate(
            liczba_autorow=Count("autor", distinct=True),
            liczba_jednostek=Count("jednostka", distinct=True),
            punkty=Sum("punkty_nazbierane"),
        )
    }
    wydzialy = Jednostka.objects.filter(parent=None, tree_id__in=sumy)
    dozwolone = jednostki_do_wgladu(request.user)
    if dozwolone is not None:
        wydzialy = wydzialy.filter(pk__in=dozwolone.values("pk"))
    return [
        {
            "wydzial": w,
            "liczba_autorow": sumy[w.tree_id]["liczba_autorow"],
            "liczba_jednostek": sumy[w.tree_id]["liczba_jednostek"],
            "punkty": sumy[w.tree_id]["punkty"],
        }
        for w in wydzialy.order_by("nazwa")
    ]


class DostepDoMetrykJednostekMixin(LoginRequiredMixin):
    """Niezalogowany → logowanie; zalogowany bez wglądu w żadną jednostkę
    → 403. Dostęp do KONKRETNEJ jednostki sprawdza widok zestawienia."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not ma_dostep_do_metryk_jednostek(
            request.user
        ):
            raise PermissionDenied("Brak dostępu do metryk jednostek.")
        return super().dispatch(request, *args, **kwargs)


class MetrykiJednostekListaView(DostepDoMetrykJednostekMixin, TemplateView):
    """Wybór jednostki — tylko widoczne dla użytkownika i mające metryki
    w wybranym okresie."""

    template_name = "ewaluacja_metryki/metryki_jednostek_lista.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["okres"] = okres_dla_request(self.request)
        wszystkie = list(jednostki_z_metrykami(self.request))
        for wiersz in wszystkie:
            wiersz["szukaj"] = tekst_wyszukiwania_jednostki(wiersz)
        fraza = self.request.GET.get("q", "").strip()
        context["q"] = fraza
        pasujace = {w["jednostka_id"] for w in filtruj_jednostki(wszystkie, fraza)}
        for wiersz in wszystkie:
            wiersz["pasuje"] = wiersz["jednostka_id"] in pasujace
        # Wszystkie wiersze idą do szablonu (niepasujące ukryte), żeby
        # filtrowanie na żywo działało też po wejściu z linku ``?q=``.
        context["jednostki"] = wszystkie
        context["liczba_wszystkich"] = len(wszystkie)
        context["liczba_pasujacych"] = len(pasujace)
        context["pokaz_wydzial"] = any(
            w.get("jednostka__wydzial__nazwa") for w in wszystkie
        )
        context["pokaz_metryki_wydzialow"] = uzywa_wydzialow(self.request) and bool(
            wydzialy_z_metrykami(self.request)
        )
        return context


class MetrykiWydzialowListaView(DostepDoMetrykJednostekMixin, TemplateView):
    """Wybór wydziału — tylko gdy uczelnia używa wydziałów."""

    template_name = "ewaluacja_metryki/metryki_wydzialow_lista.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not uzywa_wydzialow(request):
            raise Http404("Uczelnia nie używa wydziałów.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["okres"] = okres_dla_request(self.request)
        context["wydzialy"] = wydzialy_z_metrykami(self.request)
        return context


class ZestawienieMetrykView(DostepDoMetrykJednostekMixin, View):
    """Zestawienie jednej jednostki albo wydziału: domyślnie PDF,
    ``?format=html`` — podgląd jako zwykła strona serwisu."""

    template_pdf = "ewaluacja_metryki/metryki_jednostki_pdf.html"
    template_podglad = "ewaluacja_metryki/metryki_podglad.html"
    nazwa_url = None
    przedrostek_pliku = None

    def pobierz_obiekt(self, request, pk):
        return get_object_or_404(Jednostka, pk=pk)

    def zbuduj(self, obiekt, uczelnia, okres):
        raise NotImplementedError

    def get(self, request, pk):
        obiekt = self.pobierz_obiekt(request, pk)
        # Przed sprawdzeniem metryk: bez wglądu 403, a nie 404 — nie zdradzamy,
        # czy jednostka ma metryki. Wydział = korzeń drzewa, więc wgląd w niego
        # liczy się tak samo (pełne uprawnienia, wskazanie w profilu, kierownik).
        if not moze_ogladac_metryki_jednostki(request.user, obiekt):
            raise PermissionDenied("Brak dostępu do tych metryk.")
        okres = okres_dla_request(request)
        raport = self.zbuduj(obiekt, uczelnia_dla_odczytu(request), okres)
        if raport.pusty:
            raise Http404("Brak metryk ewaluacyjnych w wybranym okresie.")

        kontekst = {
            "raport": raport,
            "wersja": VERSION,
            "wygenerowano": timezone.localtime(),
            "uzytkownik": request.user,
        }
        if request.GET.get("format") == "html":
            return render(
                request,
                self.template_podglad,
                {
                    **kontekst,
                    "fonty": deklaracje_fontow(przegladarka=True),
                    "url_pdf": reverse(self.nazwa_url, args=[obiekt.pk]),
                },
            )

        html = render_to_string(
            self.template_pdf,
            {**kontekst, "fonty": deklaracje_fontow()},
            request=request,
        )

        # Leniwie: WeasyPrint wydłuża start appservera, a PDF to rzadka
        # ścieżka (tak samo jak w raport_slotow).
        from django_weasyprint.utils import DjangoURLFetcher
        from weasyprint import HTML

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        pdf = HTML(
            string=html,
            base_url=request.build_absolute_uri(),
            url_fetcher=DjangoURLFetcher(ssl_context=ssl_context),
        ).write_pdf()

        nazwa = slugify(obiekt.skrot or obiekt.nazwa)[:60] or "jednostka"
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="{self.przedrostek_pliku}_{nazwa}_'
            f'{okres.rok_od}-{okres.rok_do}.pdf"'
        )
        return response


class MetrykiJednostkiView(ZestawienieMetrykView):
    nazwa_url = "ewaluacja_metryki:metryki_jednostki"
    przedrostek_pliku = "metryki_jednostki"

    def pobierz_obiekt(self, request, pk):
        # Jednostka obca nie ma zestawienia metryk (nie ma jej też na liście).
        return get_object_or_404(Jednostka, pk=pk, skupia_pracownikow=True)

    def zbuduj(self, obiekt, uczelnia, okres):
        return zbuduj_metryki_jednostki(obiekt, uczelnia, okres)


class MetrykiWydzialuView(ZestawienieMetrykView):
    nazwa_url = "ewaluacja_metryki:metryki_wydzialu"
    przedrostek_pliku = "metryki_wydzialu"

    def pobierz_obiekt(self, request, pk):
        if not uzywa_wydzialow(request):
            raise Http404("Uczelnia nie używa wydziałów.")
        # Wydział to korzeń drzewa jednostek.
        return get_object_or_404(Jednostka, pk=pk, parent=None)

    def zbuduj(self, obiekt, uczelnia, okres):
        return zbuduj_metryki_wydzialu(obiekt, uczelnia, okres)

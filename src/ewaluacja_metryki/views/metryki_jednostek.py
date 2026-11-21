"""Metryki jednostek — zestawienie PDF dla kierownika jednostki (FD#617)."""

import ssl

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.staticfiles import finders
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
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
from ..metryki_jednostek import zbuduj_metryki_jednostki
from ..models import MetrykaAutora
from ..uczelnia_scope import scope_metryki

# Inter (OFL, podzbiór z pełną polską łacinką — static/ewaluacja_metryki/fonty).
# Pliki czytamy z dysku (file://), a nie przez HTTP: WeasyPrint nie musi wtedy
# dociągać hashowanych statyków serwisu (por. FD#405). Jeden plik na grubość:
# kroju strony (Open Sans) nie da się użyć, bo jest pocięty na zakresy znaków,
# a WeasyPrint gubi wtedy polskie litery. Brak pliku = powrót do DejaVu Sans.
GRUBOSCI_FONTU = {400: "Regular", 600: "SemiBold", 700: "Bold"}


def deklaracje_fontow():
    css = []
    for waga, nazwa in GRUBOSCI_FONTU.items():
        sciezka = finders.find(f"ewaluacja_metryki/fonty/Inter-{nazwa}.otf")
        if sciezka:
            css.append(
                "@font-face { font-family: 'Inter'; font-style: normal; "
                f"font-weight: {waga}; src: url('file://{sciezka}'); }}"
            )
    return mark_safe("\n".join(css))


def jednostki_z_metrykami(request):
    """Jednostki widoczne dla użytkownika, które mają metryki w wybranym
    okresie — z liczbą autorów i sumą punktów (lista wyboru, profil)."""
    qs = scope_metryki(
        MetrykaAutora.objects.filter(jednostka__isnull=False),
        uczelnia_dla_odczytu(request),
        okres_dla_request(request),
    )
    dozwolone = jednostki_do_wgladu(request.user)
    if dozwolone is not None:
        qs = qs.filter(jednostka__in=dozwolone)
    return (
        qs.values("jednostka_id", "jednostka__nazwa")
        .annotate(
            liczba_autorow=Count("autor", distinct=True),
            punkty=Sum("punkty_nazbierane"),
        )
        .order_by("jednostka__nazwa")
    )


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
        context["jednostki"] = jednostki_z_metrykami(self.request)
        return context


class MetrykiJednostkiView(DostepDoMetrykJednostekMixin, View):
    """Raport jednej jednostki: domyślnie PDF, ``?format=html`` — podgląd."""

    template_name = "ewaluacja_metryki/metryki_jednostki_pdf.html"

    def get(self, request, jednostka_pk):
        jednostka = get_object_or_404(Jednostka, pk=jednostka_pk)
        # Przed sprawdzeniem metryk: bez wglądu 403, a nie 404 — nie zdradzamy,
        # czy jednostka ma metryki.
        if not moze_ogladac_metryki_jednostki(request.user, jednostka):
            raise PermissionDenied("Brak dostępu do metryk tej jednostki.")
        okres = okres_dla_request(request)
        raport = zbuduj_metryki_jednostki(
            jednostka, uczelnia_dla_odczytu(request), okres
        )
        if raport.pusty:
            raise Http404("Brak metryk ewaluacyjnych tej jednostki w wybranym okresie.")

        html = render_to_string(
            self.template_name,
            {
                "raport": raport,
                "wersja": VERSION,
                "wygenerowano": timezone.localtime(),
                "uzytkownik": request.user,
                "fonty": deklaracje_fontow(),
            },
            request=request,
        )
        if request.GET.get("format") == "html":
            return HttpResponse(html)

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

        nazwa = slugify(jednostka.skrot or jednostka.nazwa)[:60] or "jednostka"
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="metryki_jednostki_{nazwa}_'
            f'{okres.rok_od}-{okres.rok_do}.pdf"'
        )
        return response

"""Raport ewaluacyjny jednostki — PDF dla kierownika (FD#617)."""

import ssl

from django.db.models import Count, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify
from django.views.generic import TemplateView, View

from bpp.models import Jednostka
from django_bpp.version import VERSION
from ewaluacja_common.okres import okres_dla_request
from raport_slotow.uczelnia_helper import uczelnia_dla_odczytu

from ..models import MetrykaAutora
from ..raport_jednostki import zbuduj_raport
from ..uczelnia_scope import scope_metryki
from .mixins import EwaluacjaRequiredMixin
from .statistics import PelneUprawnieniaEwaluacjiMixin


# Kolejność mixinów: najpierw logowanie (niezalogowany → strona logowania),
# dopiero potem pełne uprawnienia (zalogowany bez uprawnień → 403).
class RaportJednostkiListaView(
    EwaluacjaRequiredMixin, PelneUprawnieniaEwaluacjiMixin, TemplateView
):
    """Wybór jednostki — tylko te, które mają metryki w wybranym okresie."""

    template_name = "ewaluacja_metryki/raport_jednostki_lista.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        okres = okres_dla_request(self.request)
        context["okres"] = okres
        context["jednostki"] = (
            scope_metryki(
                MetrykaAutora.objects.filter(jednostka__isnull=False),
                uczelnia_dla_odczytu(self.request),
                okres,
            )
            .values("jednostka_id", "jednostka__nazwa")
            .annotate(
                liczba_autorow=Count("autor", distinct=True),
                punkty=Sum("punkty_nazbierane"),
            )
            .order_by("jednostka__nazwa")
        )
        return context


class RaportJednostkiView(EwaluacjaRequiredMixin, PelneUprawnieniaEwaluacjiMixin, View):
    """Raport jednej jednostki: domyślnie PDF, ``?format=html`` — podgląd."""

    template_name = "ewaluacja_metryki/raport_jednostki_pdf.html"

    def get(self, request, jednostka_pk):
        jednostka = get_object_or_404(Jednostka, pk=jednostka_pk)
        okres = okres_dla_request(request)
        raport = zbuduj_raport(jednostka, uczelnia_dla_odczytu(request), okres)
        if raport.pusty:
            raise Http404("Brak metryk ewaluacyjnych tej jednostki w wybranym okresie.")

        html = render_to_string(
            self.template_name,
            {
                "raport": raport,
                "wersja": VERSION,
                "wygenerowano": timezone.localtime(),
                "uzytkownik": request.user,
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
            f'attachment; filename="raport_ewaluacyjny_{nazwa}_'
            f'{okres.rok_od}-{okres.rok_do}.pdf"'
        )
        return response

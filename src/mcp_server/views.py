"""Widoki serwera MCP przeznaczone dla człowieka (nie dla klienta MCP)."""

from django.shortcuts import render
from django.views.generic import TemplateView

from bpp.models import Uczelnia
from mcp_server import instrukcje
from mcp_server.uczelnia import mcp_wlaczone_dla_requestu


class StronaMcp(TemplateView):
    """Instrukcja podłączenia klienta AI — adresy składane per host.

    Adresy MCP (``/mcp`` i ``/mcp/auth``) obsługuje warstwa ASGI
    (``mcp_server.routing.RouterHttp``) — ta strona (``/mcp/``, ze
    slashem) idzie normalnym trybem przez Django i tylko pokazuje,
    dokąd wkleić te adresy w kliencie AI.

    Wariant wynika z sesji: zalogowany ma konto, więc dostaje dostęp
    z logowaniem; niezalogowany — publiczny, z zachętą do zalogowania się.
    """

    template_name = "mcp_server/index.html"

    def get(self, request, *args, **kwargs):
        if not mcp_wlaczone_dla_requestu(request):
            # Bez adresów: instrukcja podłączenia do wyłączonej usługi
            # prowadziłaby prosto w 404 z routera.
            return render(request, "mcp_server/wylaczony.html", status=404)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        kontekst = super().get_context_data(**kwargs)
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        z_logowaniem = self.request.user.is_authenticated
        nazwa = instrukcje.nazwa_serwera(uczelnia)
        adres_publiczny = self.request.build_absolute_uri("/mcp")
        adres_z_logowaniem = self.request.build_absolute_uri("/mcp/auth")
        adres = adres_z_logowaniem if z_logowaniem else adres_publiczny

        if z_logowaniem:
            prompt = instrukcje.prompt_z_logowaniem(
                nazwa=nazwa,
                adres_publiczny=adres_publiczny,
                adres_z_logowaniem=adres_z_logowaniem,
            )
        else:
            prompt = instrukcje.prompt_publiczny(
                nazwa=nazwa, adres_publiczny=adres_publiczny
            )

        klienci = instrukcje.klienci(
            nazwa=nazwa,
            adres_publiczny=adres_publiczny,
            adres_z_logowaniem=adres_z_logowaniem,
            z_logowaniem=z_logowaniem,
        )
        kontekst.update(
            z_logowaniem=z_logowaniem,
            adres_serwera=adres,
            adres_publiczny=adres_publiczny,
            nazwa_serwera=nazwa,
            prompt_dla_asystenta=prompt,
            parametry_serwera=instrukcje.parametry_serwera(
                nazwa=nazwa, adres=adres, z_logowaniem=z_logowaniem
            ),
            klienci=klienci,
            klienci_z_logowaniem=[k.nazwa for k in klienci if k.logowanie],
            adres_bpp_mcp=instrukcje.ADRES_BPP_MCP,
        )
        return kontekst

"""Widoki serwera MCP przeznaczone dla człowieka (nie dla klienta MCP)."""

from django.shortcuts import render
from django.views.generic import TemplateView

from mcp_server.uczelnia import mcp_wlaczone_dla_requestu


class StronaMcp(TemplateView):
    """Instrukcja podłączenia klienta AI — adresy składane per host.

    Adresy MCP (``/mcp`` i ``/mcp/auth``) obsługuje warstwa ASGI
    (``mcp_server.routing.RouterHttp``) — ta strona (``/mcp/``, ze
    slashem) idzie normalnym trybem przez Django i tylko pokazuje,
    dokąd wkleić te adresy w kliencie AI.
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
        kontekst["adres_publiczny"] = self.request.build_absolute_uri("/mcp")
        kontekst["adres_z_logowaniem"] = self.request.build_absolute_uri("/mcp/auth")
        return kontekst

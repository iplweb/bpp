"""Widoki serwera MCP przeznaczone dla człowieka (nie dla klienta MCP)."""

from django.views.generic import TemplateView


class StronaMcp(TemplateView):
    """Instrukcja podłączenia klienta AI — adresy składane per host.

    Adresy MCP (``/mcp`` i ``/mcp/auth``) obsługuje warstwa ASGI
    (``mcp_server.routing.RouterHttp``) — ta strona (``/mcp/``, ze
    slashem) idzie normalnym trybem przez Django i tylko pokazuje,
    dokąd wkleić te adresy w kliencie AI.
    """

    template_name = "mcp_server/index.html"

    def get_context_data(self, **kwargs):
        kontekst = super().get_context_data(**kwargs)
        kontekst["adres_publiczny"] = self.request.build_absolute_uri("/mcp")
        kontekst["adres_z_logowaniem"] = self.request.build_absolute_uri("/mcp/auth")
        return kontekst

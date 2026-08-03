"""Wejście HTTP dla endpointu OAI-PMH z profilem OpenAIRE CRIS 1.2.

Warstwa jest celowo cienka: rozstrzyga tenanta, sprawdza przełącznik
i oddaje robotę ``cerif_export.oai.czasowniki``. Cała semantyka protokołu
siedzi tam.
"""

from django.http import Http404, HttpResponse
from django.views.generic.base import View

from bpp.models import Uczelnia
from cerif_export.oai import czasowniki


class OAICerifView(View):
    """Endpoint OAI-PMH wystawiający CERIF-XML.

    Błędy protokołu (``badVerb``, ``idDoesNotExist`` itd.) wracają jako
    poprawny dokument ``<OAI-PMH>`` ze statusem **200** — tak wymaga
    OAI-PMH 2.0 i tak sprawdza to walidator. Jedyne 404 to wyłączony
    eksport, czyli sytuacja "tu nie ma żadnego repozytorium".
    """

    def get(self, request, *args, **kwargs):
        uczelnia = self._uczelnia(request)
        zadanie = czasowniki.Zadanie(
            uczelnia=uczelnia,
            base_url=request.build_absolute_uri(request.path),
            argumenty=request.GET,
        )
        return HttpResponse(
            content=czasowniki.na_xml(czasowniki.odpowiedz(zadanie)),
            content_type="text/xml; charset=utf-8",
        )

    # OAI-PMH 2.0 wymaga obsługi zarówno GET, jak i POST
    # (application/x-www-form-urlencoded).
    def post(self, request, *args, **kwargs):
        uczelnia = self._uczelnia(request)
        zadanie = czasowniki.Zadanie(
            uczelnia=uczelnia,
            base_url=request.build_absolute_uri(request.path),
            argumenty=request.POST,
        )
        return HttpResponse(
            content=czasowniki.na_xml(czasowniki.odpowiedz(zadanie)),
            content_type="text/xml; charset=utf-8",
        )

    @staticmethod
    def _uczelnia(request):
        uczelnia = Uczelnia.objects.get_for_request(request)
        if uczelnia is None or not uczelnia.eksport_cerif_wlaczony:
            raise Http404("Eksport CERIF jest wyłączony dla tej instalacji.")
        return uczelnia

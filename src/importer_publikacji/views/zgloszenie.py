"""Widok wyboru zgłoszenia publikacji domykanego przez sesję importu.

Ścieżka C ze specu FD#443: gdy na to samo DOI istnieje więcej niż jedno
zgłoszenie, system **nie zgaduje** — operator wskazuje, które domknąć
(albo deklaruje „żadne z nich", co wycisza baner).
"""

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from ..models import ImportSession
from ..permissions import ImporterPermissionMixin
from ..zgloszenia import kandydaci_dla_sesji


class ZgloszenieWyborView(ImporterPermissionMixin, View):
    """Zwiąż sesję importu ze wskazanym zgłoszeniem (albo z żadnym).

    Bezpieczeństwo — trzy niezależne warstwy:

    * ``ImporterPermissionMixin`` — superuser albo grupa
      ``GR_WPROWADZANIE_DANYCH``,
    * ``get_scoped_or_404`` — sesja spoza uczelni redaktora daje 404,
    * walidacja wskazanego id **względem wyliczonej listy kandydatów** —
      bez niej byłby to IDOR: operator mógłby oznaczyć jako zaimportowane
      dowolne zgłoszenie w systemie (także z cudzej uczelni).
    """

    def post(self, request, session_id):
        session = self.get_scoped_or_404(ImportSession, pk=session_id)

        if request.POST.get("zadne"):
            return self._zadne(request, session)

        if request.POST.get("odepnij"):
            return self._odepnij(request, session)

        return self._wybierz(request, session)

    def _wybierz(self, request, session):
        raw = (request.POST.get("zgloszenie") or "").strip()
        if not raw.isdigit():
            return HttpResponseBadRequest(
                "Nieprawidłowy identyfikator zgłoszenia publikacji."
            )

        # IDOR guard: id MUSI pochodzić z listy kandydatów tej sesji.
        # ``kandydaci_dla_sesji`` niesie już zawężenie do uczelni (D8)
        # oraz wykluczenie statusów, których nie wolno przestemplować.
        zgloszenie = kandydaci_dla_sesji(session).filter(pk=int(raw)).first()
        if zgloszenie is None:
            return HttpResponseBadRequest(
                "Wskazane zgłoszenie nie znajduje się na liście kandydatów "
                "dla tej sesji importu."
            )

        session.zgloszenie = zgloszenie
        session.zgloszenie_odrzucone_przez_operatora = False
        session.save(
            update_fields=[
                "zgloszenie",
                "zgloszenie_odrzucone_przez_operatora",
            ]
        )
        return self._powrot(request, session)

    def _zadne(self, request, session):
        """„Żadne z nich" — wycisz baner, nie wiąż niczego."""
        session.zgloszenie = None
        session.zgloszenie_odrzucone_przez_operatora = True
        session.save(
            update_fields=[
                "zgloszenie",
                "zgloszenie_odrzucone_przez_operatora",
            ]
        )
        return self._powrot(request, session)

    def _odepnij(self, request, session):
        """„Odepnij" — operator protestuje przeciw auto-wiązaniu.

        Wiązanie znika, a baner milknie: przy jednym kandydacie nie ma
        czego innego wybrać, więc ponowne pytanie byłoby natrętne.
        """
        return self._zadne(request, session)

    def _powrot(self, request, session):
        """Wróć na ekran, z którego przyszedł POST.

        ``next`` z POST-a, w drugiej kolejności ``Referer`` — oba
        walidowane (żadnych otwartych przekierowań). Ostatecznie krok
        weryfikacji danej sesji.
        """
        url = self._bezpieczny_url(request, request.POST.get("next"))
        if url is None:
            url = self._bezpieczny_url(request, request.headers.get("Referer"))
        if url is None:
            url = reverse(
                "importer_publikacji:verify",
                kwargs={"session_id": session.pk},
            )

        if request.headers.get("HX-Request"):
            response = HttpResponse(status=200)
            response["HX-Redirect"] = url
            return response
        return HttpResponseRedirect(url)

    @staticmethod
    def _bezpieczny_url(request, url):
        if not url:
            return None
        if url_has_allowed_host_and_scheme(
            url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return url
        return None

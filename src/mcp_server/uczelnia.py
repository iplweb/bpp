"""Fail-closed rozstrzyganie uczelni dla nagłówka ``Host`` żądania MCP.

Na ścieżce ``/mcp`` **Host jest kontrolą dostępu** (spec §7.2): to on decyduje,
którą ``Uczelnia`` zobaczy ``BramkaApiV1``, ``scope_rekord_do_uczelni``
i ``UkryjStatusyKorektyMixin`` w żądaniu wewnętrznym. A wszystkie trzy są
zbudowane tak, że **brak uczelni znaczy „nie ograniczaj”**:

* ``BramkaApiV1.has_permission`` przy ``uczelnia is None`` zwraca ``True``
  BEZWARUNKOWO — także gdy administrator ustawił ``api_v1_wlaczone=False``
  albo ``api_v1_tylko_zalogowani=True`` (``api_v1/permissions.py``);
* ``scope_rekord_do_uczelni`` staje się no-op (``bpp/util/uczelnia_scope.py``);
* ``UkryjStatusyKorektyMixin`` przestaje wykluczać ukryte statusy korekty
  (``api_v1/viewsets/common.py``).

To jest bezpieczne dla zwykłego ruchu HTTP, bo tam nagłówek ``Host`` przechodzi
przez ``ALLOWED_HOSTS``, a ``ALLOWED_HOSTS`` na produkcji zawiera hosty
INFRASTRUKTURALNE (``127.0.0.1``, ``appserver``, ``appserver:8000`` —
``settings/production.py``), które nie mają swojego ``Site``. Dla nich
``Uczelnia.objects.get_for_request`` schodzi na fallback ``SITE_ID`` albo
zwraca ``None``: w instalacji wielouczelnianej ``curl -H 'Host: appserver'``
obchodziłby wyłącznik API i filtr ukrytych statusów.

Dlatego na tej jednej ścieżce host, który **nie identyfikuje jednoznacznie
uczelni**, jest odrzucany, zamiast obsłużony z otwartą bramką.

Dlaczego sprawdzenie jest PER ŻĄDANIE, a nie w allowliście transportowej
(``aplikacja._dozwolone_hosty``): tamta jest liczona przy budowie aplikacji,
czyli przy imporcie ``django_bpp.asgi``, a import modułu ASGI nie może zależeć
od dostępnej bazy. Powiązanie host→``Site``→``Uczelnia`` to DANE, nie
konfiguracja — administrator dokłada i zabiera je bez restartu procesu, więc
tylko odczyt per żądanie mówi prawdę. Allowlista transportowa zostaje tym, czym
jest w SDK: ochroną przed DNS rebindingiem, a nie kontrolą wielotenantową.
"""

from __future__ import annotations

from asgiref.sync import sync_to_async
from django.db import close_old_connections


class _ZadanieZHostem:
    """Namiastka ``HttpRequest`` — ``get_for_request`` czyta tylko ``get_host``."""

    def __init__(self, host: str) -> None:
        self._host = host

    def get_host(self) -> str:
        return self._host


def _rozstrzygalny(host: str) -> bool:
    """Czy ``host`` jednoznacznie wskazuje jedną ``Uczelnia``?

    Dwie ścieżki, obie zamierzone:

    1. **Host ma swój ``Site``** — normalna sytuacja instalacji
       wielouczelnianej. Wtedy pytamy ``get_for_request`` dokładnie tak, jak
       zrobi to później ``BramkaApiV1``, i wymagamy niepustego wyniku. ``Site``
       bez podpiętej uczelni w instalacji z wieloma uczelniami da ``None`` →
       odmowa.
    2. **Host nie ma ``Site``** — dopuszczalne WYŁĄCZNIE w instalacji
       jednouczelnianej, gdzie fallback na ``SITE_ID`` (a dalej na „jedyną
       uczelnię”) jest legalny i tak działa cały serwis. Warunkiem jest, żeby
       uczelnia w bazie była dokładnie jedna: przy zerze nie ma czego serwować
       (świeża instalacja, niedokończony kreator), a przy dwóch i więcej host
       niczego nie rozstrzyga i wybór byłby zgadywaniem.

    ``close_old_connections`` jak w ``mcp_server.auth``: biegniemy poza cyklem
    żądania Django, więc sygnały ``request_started/finished`` nie sprzątają
    połączeń za nas.
    """
    from django.contrib.sites.models import Site

    from bpp.models import Uczelnia

    hostname = host.split(":")[0]
    close_old_connections()
    try:
        if (
            not Site.objects.filter(domain=hostname).exists()
            and Uczelnia.objects.count() != 1
        ):
            return False
        return Uczelnia.objects.get_for_request(_ZadanieZHostem(host)) is not None
    finally:
        close_old_connections()


#: Wersja asynchroniczna — warstwa ASGI nie ma pętli, w której wolno jej
#: blokować na ORM. ``thread_sensitive=False`` jak przy weryfikacji tokenu:
#: to czysty odczyt, bez współdzielonego stanu transakcyjnego z wołającym.
host_rozstrzyga_uczelnie = sync_to_async(_rozstrzygalny, thread_sensitive=False)

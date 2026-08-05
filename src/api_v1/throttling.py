"""Throttling dla kosztownych endpointów wyszukiwania API ``/api/v1/``.

Globalny throttling API pozostaje WYŁĄCZONY (świadoma decyzja: mpasternak,
6.06.2020 — patrz ``settings/base.py``). Limitujemy WYŁĄCZNIE drogie
endpointy wyszukiwania, które anonim może wywoływać po dużych tabelach:

* ``/api/v1/szukaj/`` — pełnotekstowe wyszukiwanie po wszystkich publikacjach,
* ``/api/v1/autor/`` — filtr ``nazwisko__icontains`` (skan bez indeksu prefiksu).

Osobne, ostrzejsze limity anon/user (``AnonRateThrottle`` liczy po IP i tylko
dla niezalogowanych, ``UserRateThrottle`` — tylko dla zalogowanych; razem dają
rozdzielne progi). Rate'y w ``settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]``
(klucze == ``scope``).

Wymaga działającego backendu cache (prod: Redis). Pod ``DummyCache`` (dev/test)
throttling jest no-op — akceptowalne, bo środowiska te nie potrzebują limitów.
"""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class SearchAnonThrottle(AnonRateThrottle):
    """Limit dla anonimowych wywołań kosztownych endpointów wyszukiwania."""

    scope = "search_anon"


class SearchUserThrottle(UserRateThrottle):
    """Limit dla zalogowanych wywołań kosztownych endpointów wyszukiwania."""

    scope = "search_user"

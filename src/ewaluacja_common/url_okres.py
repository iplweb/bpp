"""Okres ewaluacji w adresie URL stron ewaluacji.

Strony aplikacji z ``APLIKACJE_W_URL`` mają okres w ścieżce zaraz po
prefiksie aplikacji, np. ``/ewaluacja_liczba_n/2026-2030/udzialy-za-calosc/``
— taki link można komuś wysłać i otworzy się dokładnie ten okres.

Jak to działa (bez przerabiania setek ``{% url %}``):

- dla każdego okresu budujemy osobny URLconf: kopię ``ROOT_URLCONF``,
  w której te aplikacje są podpięte pod ``<prefiks><rok_od>-<rok_do>/``;
- ``OkresWUrlMiddleware`` przy adresie z okresem ustawia ``request.urlconf``
  na URLconf tego okresu, więc ``reverse()`` / ``{% url %}`` w tym żądaniu
  same dokładają okres do linków;
- wejście na stronę z paskiem okresu BEZ okresu w adresie (np. z górnego
  menu) przekierowuje przeglądarkę na adres z okresem wybranym ostatnio.

Okres z adresu ma pierwszeństwo przed sesją — to usuwa wyścig, w którym
odpytywanie statusu (HTMX co 2 s) zapisywało sesję ze starym okresem
i nadpisywało świeży wybór.
"""

import re
import sys
import types

from django.conf import settings
from django.http import HttpResponseRedirect, QueryDict
from django.urls import URLResolver, include, path
from django.urls.exceptions import Resolver404

#: Prefiksy URL (z ``ROOT_URLCONF``) aplikacji, które mają okres w adresie.
APLIKACJE_W_URL = (
    "ewaluacja_metryki/",
    "ewaluacja_liczba_n/",
    "ewaluacja_optymalizacja/",
    "ewaluacja_dwudyscyplinowcy/",
    "snapshot_odpiec/",
    "oswiadczenia/",
    "pbn-wysylka-oswiadczen/",
    "komparator_pbn/",
    "komparator-zrodel-pbn/",
    "komparator-pbn-udzialy/",
    "komparator-publikacji-pbn/",
    "deduplikator_autorow/",
)

#: Parametry GET, których linki paska okresu NIE przenoszą (patrz
#: ``adres_dla_okresu(bez_lat=True)``), na każdej stronie z paskiem:
#: numer strony (w nowym okresie wracamy na pierwszą) i pojedynczy rok
#: (zostałby rok spoza nowego okresu).
PARAMETRY_GUBIONE = ("page", "rok")

#: Jak wyżej, ale dla wybranych aplikacji (prefiks → nazwy): ręcznie wpisany
#: zakres lat komparatorów PBN.
PARAMETRY_LAT = {
    "komparator-zrodel-pbn/": ("rok_od", "rok_do"),
    "komparator-pbn-udzialy/": ("rok_min", "rok_max"),
    "komparator-publikacji-pbn/": ("year_min", "year_max"),
}

_SLUG = r"(?P<rok_od>\d{4})-(?P<rok_do>\d{4})"
_ADRES = re.compile(
    r"^/(?P<prefiks>"
    + "|".join(re.escape(p) for p in APLIKACJE_W_URL)
    + r")(?:"
    + _SLUG
    + r"/)?(?P<reszta>.*)$"
)

_urlconfy = {}


def _prefiks_wzorca(resolver):
    return str(resolver.pattern).lstrip("^")


def _zbuduj_urlconf(okres):
    """Moduł URLconf okresu (rejestrowany w ``sys.modules``, bo Django
    trzyma resolvery w cache po nazwie modułu)."""
    from importlib import import_module

    root = import_module(settings.ROOT_URLCONF)
    wzorce = []
    for wzorzec in root.urlpatterns:
        if (
            isinstance(wzorzec, URLResolver)
            and _prefiks_wzorca(wzorzec) in APLIKACJE_W_URL
        ):
            wzorzec = path(
                f"{_prefiks_wzorca(wzorzec)}{okres.slug}/",
                include(
                    (wzorzec.urlconf_module, wzorzec.app_name),
                    namespace=wzorzec.namespace,
                ),
            )
        wzorce.append(wzorzec)

    nazwa = f"{settings.ROOT_URLCONF}__okres_{okres.rok_od}_{okres.rok_do}"
    modul = types.ModuleType(nazwa)
    modul.urlpatterns = wzorce
    for handler in ("handler400", "handler403", "handler404", "handler500"):
        if hasattr(root, handler):
            setattr(modul, handler, getattr(root, handler))
    sys.modules[nazwa] = modul
    return nazwa


def urlconf_dla_okresu(okres):
    klucz = (settings.ROOT_URLCONF, okres.rok_od, okres.rok_do)
    if klucz not in _urlconfy:
        _urlconfy[klucz] = _zbuduj_urlconf(okres)
    return _urlconfy[klucz]


def reverse_w_okresie(viewname, okres, args=None, kwargs=None):
    """``reverse()`` adresu strony aplikacji z okresem w URL dla podanego
    okresu — niezależnie od okresu bieżącego żądania (np. linki do metryk
    autora z różnych okresów na jednej stronie)."""
    from django.urls import reverse

    return reverse(
        viewname, urlconf=urlconf_dla_okresu(okres), args=args, kwargs=kwargs
    )


def rozbierz_adres(sciezka):
    """``(prefiks, slug albo None, reszta)`` dla adresu strony aplikacji
    z okresem w URL, inaczej ``None``."""
    m = _ADRES.match(sciezka)
    if m is None:
        return None
    slug = f"{m['rok_od']}-{m['rok_do']}" if m["rok_od"] else None
    return m["prefiks"], slug, m["reszta"]


def adres_dla_okresu(request, okres, bez_lat=False):
    """Bieżący adres (ze ścieżką i query stringiem) przełączony na ``okres``
    albo ``None``, gdy strona nie należy do aplikacji z okresem w URL.

    ``bez_lat=True`` (linki paska okresu): z adresu znikają numer strony,
    pojedynczy rok (``PARAMETRY_GUBIONE``) i ręcznie wpisany zakres lat
    (``PARAMETRY_LAT``), żeby po przełączeniu okresu strona pokazała pierwszą
    stronę danych nowego okresu. Pozostałe parametry zostają."""
    czesci = rozbierz_adres(request.path_info)
    if czesci is None:
        return None
    prefiks, _slug, reszta = czesci
    script_name = request.path[: len(request.path) - len(request.path_info)]
    adres = f"{script_name}/{prefiks}{okres.slug}/{reszta}"
    zapytanie = request.META.get("QUERY_STRING", "")
    if bez_lat and zapytanie:
        parametry = QueryDict(zapytanie, mutable=True)
        gubione = PARAMETRY_GUBIONE + PARAMETRY_LAT.get(prefiks, ())
        # Adres bez gubionych parametrów zostaje co do znaku.
        if any(nazwa in parametry for nazwa in gubione):
            for nazwa in gubione:
                parametry.pop(nazwa, None)
            zapytanie = parametry.urlencode()
    if zapytanie:
        adres += "?" + zapytanie
    return adres


class OkresWUrlMiddleware:
    """Okres ewaluacji z adresu URL (patrz docstring modułu). Musi stać po
    ``AuthenticationMiddleware`` (zapamiętuje wybór użytkownika)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        czesci = rozbierz_adres(request.path_info)
        if czesci is not None:
            prefiks, slug, _reszta = czesci
            if slug is not None:
                self._okres_z_adresu(request, slug)
            elif self._przekierowac(request):
                from ewaluacja_common.okres import okres_dla_request

                okres = okres_dla_request(request)
                if okres is not None:
                    return HttpResponseRedirect(adres_dla_okresu(request, okres))
        return self.get_response(request)

    @staticmethod
    def _okres_z_adresu(request, slug):
        from ewaluacja_common.models import OkresEwaluacji
        from ewaluacja_common.okres import KLUCZ_SESJI, ustaw_okres

        rok_od, rok_do = (int(x) for x in slug.split("-"))
        okres = OkresEwaluacji.objects.filter(rok_od=rok_od, rok_do=rok_do).first()
        if okres is None:
            return  # nieznany okres — domyślny URLconf da 404
        request.urlconf = urlconf_dla_okresu(okres)
        # Zapamiętaj jako ostatni wybór (zapis tylko przy zmianie).
        if getattr(request, "session", {}).get(KLUCZ_SESJI) != okres.pk:
            ustaw_okres(request, okres)
        request._okres_ewaluacji = okres

    @staticmethod
    def _przekierowac(request):
        """Tylko nawigacja przeglądarki (nie HTMX/fetch, nie POST) na strony
        z paskiem okresu — przekierowanie na adres z okresem."""
        if request.method != "GET":
            return False
        if request.headers.get("Sec-Fetch-Mode") != "navigate":
            return False
        if request.headers.get("HX-Request"):
            return False
        from django.urls import resolve

        from ewaluacja_common.okres import pokazac_pasek_okresu

        try:
            dopasowanie = resolve(request.path_info)
        except Resolver404:
            return False
        return pokazac_pasek_okresu(dopasowanie)

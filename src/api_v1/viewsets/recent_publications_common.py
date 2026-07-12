"""Wspólna logika endpointów embedu publikacji (autor / jednostka).

Endpointy zwracają publiczną, odfiltrowaną listę publikacji encji w formacie
JSON konsumowanym przez loader ``bpp-publikacje.js``. Współdzielą:

* filtr widoczności (kontekst ``"api"`` z :class:`bpp.models.Uczelnia`),
* parametry zapytania ``limit`` / ``rok_od`` / ``rok_do``,
* sortowanie ``-rok, -ostatnio_zmieniony`` + ``distinct`` + wąskie ``only``,
* serializację pozycji i nagłówki CORS (osadzanie cross-origin).
"""

from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework.response import Response

from bpp.models import Uczelnia
from bpp.models.cache import Rekord

DOMYSLNY_LIMIT = 25
MAKS_LIMIT = 100


def _int_param(request, nazwa, default=None):
    """Parsuj nieujemny parametr całkowity; przy błędnym wejściu → ``default``."""
    surowy = request.query_params.get(nazwa)
    if surowy is None or surowy == "":
        return default
    try:
        return int(surowy)
    except (TypeError, ValueError):
        return default


def _url_publikacji(pub, request):
    if pub.slug:
        return request.build_absolute_uri(
            reverse("bpp:browse_praca_by_slug", args=[pub.slug])
        )
    # Fallback dla rekordów bez slug
    return request.build_absolute_uri(
        reverse("bpp:browse_praca", args=[pub.id[0], pub.id[1]])
    )


def _ustaw_cors(resp):
    resp["Access-Control-Allow-Origin"] = "*"
    resp["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    resp["Access-Control-Allow-Headers"] = "Content-Type, Range"
    resp["Access-Control-Expose-Headers"] = "Content-Disposition, Content-Length"
    resp["Vary"] = "Origin"


def odpowiedz_z_publikacjami(request, base_qs, naglowek):
    """Zbuduj odpowiedź embedu z queryset-u :class:`Rekord` zawężonego do encji.

    :param base_qs: queryset ``Rekord`` ograniczony już do autora/jednostki.
    :param naglowek: dict z metadanymi encji (np. ``{"autor_id": ...,
        "autor_nazwa": ...}``) wstrzykiwany na początek odpowiedzi.
    """
    # Ta sama polityka widoczności API co /szukaj/ i /zapytanie/rekord/:
    # izolacja uczelni + ukryte statusy + rekordy nie_eksportuj_przez_api.
    # (wcześniej tylko ukryte statusy — L1: wyciek nie_eksportuj_przez_api +
    # brak izolacji multi-host na AllowAny+CORS* embedzie).
    from api_v1.scoping import scope_rekord_api
    from api_v1.viewsets.szukaj import MODELE_DETAIL_VIEWNAME

    uczelnia = Uczelnia.objects.get_for_request(request)
    qs = scope_rekord_api(base_qs, uczelnia, MODELE_DETAIL_VIEWNAME)

    rok_od = _int_param(request, "rok_od")
    if rok_od is not None:
        qs = qs.filter(rok__gte=rok_od)
    rok_do = _int_param(request, "rok_do")
    if rok_do is not None:
        qs = qs.filter(rok__lte=rok_do)

    limit = _int_param(request, "limit", default=DOMYSLNY_LIMIT)
    limit = max(1, min(limit, MAKS_LIMIT))

    # distinct: encja może wystąpić na rekordzie wielokrotnie (np. autor i
    # redaktor); only: bez ~40 zbędnych kolumn tabeli mat (m.in. tsvector
    # search_index).
    publikacje = (
        qs.order_by("-rok", "-ostatnio_zmieniony")
        .distinct()
        .only("id", "slug", "rok", "opis_bibliograficzny_cache", "ostatnio_zmieniony")[
            :limit
        ]
    )

    wynik = [
        {
            "id": str(pub.id),
            "opis_bibliograficzny": pub.opis_bibliograficzny_cache,
            "rok": pub.rok,
            "ostatnio_zmieniony": pub.ostatnio_zmieniony,
            "url": _url_publikacji(pub, request),
        }
        for pub in publikacje
    ]

    resp = Response({**naglowek, "count": len(wynik), "publications": wynik})
    _ustaw_cors(resp)
    return resp


def pobierz_encje_lub_404(model, lookup, **dodatkowe_filtry):
    """Rozwiąż encję po numerycznym ``pk`` LUB po ``slug``.

    Router DRF generuje retrieve z ``lookup_value_regex = [^/.]+``, który łapie
    też slugi, więc identyfikator rozróżniamy tutaj (a nie kolejnością URL-i).
    Krawędziowo: czysto numeryczny slug zostanie potraktowany jako ``pk``.
    """
    qs = model.objects.filter(**dodatkowe_filtry)
    if str(lookup).isdigit():
        return get_object_or_404(qs, pk=lookup)
    return get_object_or_404(qs, slug=lookup)


def queryset_rekordow():
    """Bazowy menedżer rekordów (ułatwia mockowanie/testy)."""
    return Rekord.objects

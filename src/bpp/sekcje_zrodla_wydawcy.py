"""Sekcje stron źródła i wydawcy: najczęściej publikujący autorzy, jednostki
z największą liczbą prac oraz aktualny poziom wydawcy z wykazu.

Liczenie w SQL (agregaty na ``bpp_autorzy_mat``): jedno zapytanie na ranking
autorów + jedno po obiekty ``Autor``, jedno na ranking jednostek. Prace
o statusach korekty ukrytych przed oglądającym nie są liczone (ten sam kanał
„podglad” co strona autora — ``ukryte_statusy_podgladu``).

Widoki (``ZrodloView``, ``WydawcaView``) wołają tylko ``sekcje_zrodla`` /
``sekcje_wydawcy`` i dokładają wynik do kontekstu.
"""

from django.db.models import Count

from bpp.profil_autora_dane import ukryte_statusy_podgladu
from bpp.util.ukryte_statusy import widoczni_autorzy

#: Ile pozycji pokazuje każda z sekcji.
LIMIT_SEKCJI = 10

#: Numer poziomu wydawcy → zapis rzymski w znaczku nagłówka.
POZIOM_RZYMSKI = {1: "I", 2: "II"}


def _autorzy_rekordow(filtr_rekordu, request):
    """``Autorzy`` (powiązania autor–rekord) ograniczone do rekordów z
    ``filtr_rekordu`` (lookupy z prefiksem ``rekord__``), bez rekordów
    o ukrytych statusach korekty."""
    from bpp.models.cache import Autorzy

    qs = Autorzy.objects.filter(**filtr_rekordu)
    statusy = ukryte_statusy_podgladu(request)
    if statusy:
        qs = qs.exclude(rekord__status_korekty_id__in=statusy)
    return qs


def najczesciej_publikujacy_autorzy(filtr_rekordu, request, limit=LIMIT_SEKCJI):
    """Lista ``{"autor": Autor, "liczba": int}`` — autorzy z największą
    liczbą (różnych) prac spełniających ``filtr_rekordu``, malejąco.

    To ranking, więc pomija autorów z ``pokazuj_w_rankingu=False`` (redakcja
    widzi wszystkich — ``widoczni_autorzy``). Linki (wyszukiwanie, strona
    autora) szablon i tak wystawia wg ``pokazuj_w_wyszukiwaniu`` /
    ``pokazuj_strone_autora``. Dwa zapytania: ranking + obiekty autorów.
    """
    from bpp.models import Autor

    qs = widoczni_autorzy(
        _autorzy_rekordow(filtr_rekordu, request),
        request,
        lookup="autor__pokazuj_w_rankingu",
    )
    wiersze = list(
        qs.values("autor_id")
        .annotate(liczba=Count("rekord_id", distinct=True))
        .order_by("-liczba", "autor__nazwisko", "autor__imiona", "autor_id")[:limit]
    )
    if not wiersze:
        return []
    autorzy = Autor.objects.select_related("tytul").in_bulk(
        [w["autor_id"] for w in wiersze]
    )
    return [
        {"autor": autorzy[w["autor_id"]], "liczba": w["liczba"]}
        for w in wiersze
        if w["autor_id"] in autorzy
    ]


def najczestsze_jednostki(filtr_rekordu, request, limit=LIMIT_SEKCJI):
    """Lista ``{"pk", "nazwa", "slug", "liczba"}`` — jednostki (widoczne,
    skupiające pracowników, czyli bez „obcej”) z największą liczbą różnych
    prac spełniających ``filtr_rekordu``. Jedno zapytanie."""
    wiersze = (
        _autorzy_rekordow(filtr_rekordu, request)
        .filter(jednostka__widoczna=True, jednostka__skupia_pracownikow=True)
        .values("jednostka_id", "jednostka__nazwa", "jednostka__slug")
        .annotate(liczba=Count("rekord_id", distinct=True))
        .order_by("-liczba", "jednostka__nazwa")[:limit]
    )
    return [
        {
            "pk": w["jednostka_id"],
            "nazwa": w["jednostka__nazwa"],
            "slug": w["jednostka__slug"],
            "liczba": w["liczba"],
        }
        for w in wiersze
    ]


def _sekcje(filtr_rekordu, request):
    return {
        "top_autorzy": najczesciej_publikujacy_autorzy(filtr_rekordu, request),
        "top_jednostki": najczestsze_jednostki(filtr_rekordu, request),
    }


def sekcje_zrodla(zrodlo, request):
    """Kontekst sekcji strony źródła (``top_autorzy``, ``top_jednostki``)."""
    return _sekcje({"rekord__zrodlo_id": zrodlo.pk}, request)


def aktualny_poziom_wydawcy(wydawca):
    """Słownik ``{"rok", "poziom", "rzymski"}`` dla najnowszego roku
    z ``Poziom_Wydawcy`` albo ``None`` — gdy wpisów brak lub w najnowszym
    roku poziom jest nieokreślony (wydawca wypadł z wykazu; starszy poziom
    byłby mylący). Jedno zapytanie."""
    ostatni = wydawca.poziom_wydawcy_set.order_by("-rok").first()
    if ostatni is None or ostatni.poziom not in POZIOM_RZYMSKI:
        return None
    return {
        "rok": ostatni.rok,
        "poziom": ostatni.poziom,
        "rzymski": POZIOM_RZYMSKI[ostatni.poziom],
    }


def sekcje_wydawcy(wydawca, request):
    """Kontekst sekcji strony wydawcy: ``top_autorzy``, ``top_jednostki``
    (prace wydawcy razem z aliasami) i ``aktualny_poziom``."""
    ctx = _sekcje({"rekord__wydawca_id__in": wydawca.wszystkie_pk()}, request)
    ctx["aktualny_poziom"] = aktualny_poziom_wydawcy(wydawca)
    return ctx

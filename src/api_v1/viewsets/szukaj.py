"""Endpoint wyszukiwania publikacji ``GET /api/v1/szukaj/``.

Wystawia istniejący silnik pełnotekstowy BPP (``Rekord.objects.fulltext_filter``)
w warstwie DRF. Read-only, anonimowe, stronicowane (globalny LimitOffset).
Bez nowej logiki wyszukiwania i bez zmian schematu — patrz spec Faza 0.
"""

from django.contrib.contenttypes.models import ContentType
from rest_framework import mixins, viewsets

from api_v1.scoping import scope_rekord_api
from api_v1.serializers.szukaj import SzukajSerializer
from api_v1.throttling import SearchAnonThrottle, SearchUserThrottle
from bpp.models import (
    Patent,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from bpp.models.cache import Rekord

# Pięć typów źródłowych spinanych przez mat-view ``Rekord`` → viewname
# typowanego detalu w API. Każdy z 5 typów ma endpoint (brak „typu spoza mapy").
MODELE_DETAIL_VIEWNAME = {
    Wydawnictwo_Ciagle: "api_v1:wydawnictwo_ciagle-detail",
    Wydawnictwo_Zwarte: "api_v1:wydawnictwo_zwarte-detail",
    Patent: "api_v1:patent-detail",
    Praca_Doktorska: "api_v1:praca_doktorska-detail",
    Praca_Habilitacyjna: "api_v1:praca_habilitacyjna-detail",
}

#: Minimalny zestaw kolumn ``Rekord`` potrzebny SzukajSerializer-owi.
#: Mat-view ``bpp_rekord_mat`` ma ~50 kolumn, w tym tsvector ``search_index``
#: (największa z nich) — bez ``only()`` każdy wiersz strony ciągnie je
#: wszystkie. ``tytul_oryginalny_sort`` jest tu nie dla serializera, tylko
#: dlatego, że sortuje po nim ORDER BY (przy DISTINCT Postgres wymaga, by
#: wyrażenia sortujące były na liście SELECT).
POLA_REKORDU_DLA_SZUKAJ = (
    "id",
    "slug",
    "rok",
    "opis_bibliograficzny_cache",
    "ostatnio_zmieniony",
    "tytul_oryginalny",
    "tytul_oryginalny_sort",
)


class SzukajViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Rankowane wyszukiwanie pełnotekstowe po wszystkich typach publikacji.

    Parametry zapytania:

    * ``q`` — tekst zapytania (składnia websearch: cudzysłowy, minus); brak/
      puste ``q`` → pusta lista (``fulltext_empty``), nie błąd,
    * ``rok_od`` / ``rok_do`` — zawężenie po roku (włącznie),
    * ``limit`` / ``offset`` — standardowa paginacja LimitOffset.
    """

    serializer_class = SzukajSerializer
    # Kosztowny endpoint wyszukiwania — opt-in throttling (globalny wyłączony).
    throttle_classes = [SearchAnonThrottle, SearchUserThrottle]

    def _int_param(self, nazwa):
        """Parametr całkowity; brak/puste/niepoprawne wejście → ``None``.

        Parsuje wartość jako ``int`` (ujemne przechodzą — brak walidacji znaku).
        """
        surowy = self.request.query_params.get(nazwa)
        if surowy is None or surowy == "":
            return None
        try:
            return int(surowy)
        except (TypeError, ValueError):
            return None

    def _mapa_contenttype_viewname(self):
        """content_type_id → viewname detalu, rozwiązywane w RUNTIME."""
        return {
            ContentType.objects.get_for_model(model).pk: viewname
            for model, viewname in MODELE_DETAIL_VIEWNAME.items()
        }

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["contenttype_to_viewname"] = self._mapa_contenttype_viewname()
        return context

    def get_queryset(self):
        # Pusty/niepoprawny ``q`` → fulltext_empty() (pusta lista, nie 500).
        q = self.request.query_params.get("q")
        qs = Rekord.objects.fulltext_filter(q)

        rok_od = self._int_param("rok_od")
        if rok_od is not None:
            qs = qs.filter(rok__gte=rok_od)
        rok_do = self._int_param("rok_do")
        if rok_do is not None:
            qs = qs.filter(rok__lte=rok_do)

        # Polityka widoczności API (multi-uczelnia + ukryte statusy +
        # nie_eksportuj_przez_api) — wspólne źródło z /zapytanie/rekord/,
        # patrz api_v1.scoping.scope_rekord_api. Gdy brak mapowania
        # Site→Uczelnia (uczelnia is None) — scoping uczelni jest no-op.
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        qs = scope_rekord_api(qs, uczelnia, MODELE_DETAIL_VIEWNAME)

        # Nie ciągnij tsvectora ``search_index`` ani ~40 kolumn mat-view.
        qs = qs.only(*POLA_REKORDU_DLA_SZUKAJ)

        # Deterministyczny tiebreaker: rank bywa remisowy → sam rank gubiłby/
        # dublował rekordy przy paginacji offsetem.
        return qs.order_by("-search_index__rank", "tytul_oryginalny_sort", "id")

"""Endpoint wyszukiwania publikacji ``GET /api/v1/szukaj/``.

Wystawia istniejący silnik pełnotekstowy BPP (``Rekord.objects.fulltext_filter``)
w warstwie DRF. Read-only, anonimowe, stronicowane (globalny LimitOffset).
Bez nowej logiki wyszukiwania i bez zmian schematu — patrz spec Faza 0.
"""

from django.contrib.contenttypes.models import ContentType
from rest_framework import mixins, viewsets

from api_v1.serializers.szukaj import SzukajSerializer
from bpp.models import (
    Patent,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from bpp.models.cache import Rekord
from bpp.util.uczelnia_scope import scope_rekord_do_uczelni

# Pięć typów źródłowych spinanych przez mat-view ``Rekord`` → viewname
# typowanego detalu w API. Każdy z 5 typów ma endpoint (brak „typu spoza mapy").
MODELE_DETAIL_VIEWNAME = {
    Wydawnictwo_Ciagle: "api_v1:wydawnictwo_ciagle-detail",
    Wydawnictwo_Zwarte: "api_v1:wydawnictwo_zwarte-detail",
    Patent: "api_v1:patent-detail",
    Praca_Doktorska: "api_v1:praca_doktorska-detail",
    Praca_Habilitacyjna: "api_v1:praca_habilitacyjna-detail",
}


class SzukajViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Rankowane wyszukiwanie pełnotekstowe po wszystkich typach publikacji.

    Parametry zapytania:

    * ``q`` — tekst zapytania (składnia websearch: cudzysłowy, minus); brak/
      puste ``q`` → pusta lista (``fulltext_empty``), nie błąd,
    * ``rok_od`` / ``rok_do`` — zawężenie po roku (włącznie),
    * ``limit`` / ``offset`` — standardowa paginacja LimitOffset.
    """

    serializer_class = SzukajSerializer

    def _int_param(self, nazwa):
        """Nieujemny parametr całkowity; błędne/puste wejście → ``None``."""
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

        # Multi-uczelnia: zawężamy jak frontowa wyszukiwarka „/". Gdy brak
        # mapowania Site→Uczelnia (uczelnia is None) — scope_rekord_do_uczelni
        # jest no-op, więc zachowujemy się jak reszta API (bez zawężenia).
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        qs = scope_rekord_do_uczelni(qs, uczelnia)
        if uczelnia is not None:
            qs = qs.exclude(status_korekty_id__in=uczelnia.ukryte_statusy("api"))

        # ``nie_eksportuj_przez_api`` NIE istnieje na Rekord (tylko na modelach
        # źródłowych). Wykluczamy per-content-type subquery na TupleField:
        # (id[0]==ct.pk AND id[1] IN <oflagowane pk>). Subquery tylko po
        # oflagowanych → tanio.
        for model in MODELE_DETAIL_VIEWNAME:
            ct_pk = ContentType.objects.get_for_model(model).pk
            oflagowane = model.objects.filter(nie_eksportuj_przez_api=True).values("pk")
            qs = qs.exclude(id__0=ct_pk, id__1__in=oflagowane)

        # Nie ciągnij tsvectora ``search_index`` ani ~40 kolumn mat-view.
        qs = qs.only(
            "id",
            "slug",
            "rok",
            "opis_bibliograficzny_cache",
            "ostatnio_zmieniony",
            "tytul_oryginalny",
            "tytul_oryginalny_sort",
        )

        # Deterministyczny tiebreaker: rank bywa remisowy → sam rank gubiłby/
        # dublował rekordy przy paginacji offsetem.
        return qs.order_by("-search_index__rank", "tytul_oryginalny_sort", "id")

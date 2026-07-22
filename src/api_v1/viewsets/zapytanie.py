"""Autoryzowane wyszukiwanie DjangoQL po API — ``GET /api/v1/zapytanie/<model>/``.

Wystawia istniejący silnik ``apply_search`` (schemat ``RekordLLMSchema``) w
warstwie DRF, read-only, gate'owane ``MoznaUzywacZapytania``. Kształt wyników:
kompaktowa płaska projekcja per model.
"""

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldError, ValidationError
from django.db.utils import OperationalError
from djangoql.exceptions import DjangoQLError
from djangoql.queryset import apply_search
from rest_framework import mixins, viewsets
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from api_v1.permissions import MoznaUzywacZapytania
from api_v1.scoping import scope_rekord_api
from api_v1.serializers.szukaj import SzukajSerializer
from api_v1.serializers.zapytanie import (
    AutorKompaktSerializer,
    AutorzyKompaktSerializer,
)
from api_v1.viewsets.szukaj import MODELE_DETAIL_VIEWNAME
from bpp.djangoql_errors import error_payload
from bpp.djangoql_schema import RekordLLMSchema
from bpp.models import Autor, Uczelnia
from bpp.models.cache import Autorzy, Rekord
from bpp.util.statement_timeout import statement_timeout
from bpp.util.uczelnia_scope import (
    scope_autor_do_uczelni,
    scope_autorzy_do_uczelni,
)

#: Twardy cap paginacji — jedno żądanie nie ciągnie całej bazy.
MAKS_LIMIT = 100

#: Twardy statement_timeout dla DjangoQL po API (ms).
ZAPYTANIE_TIMEOUT_MS = 8000


class _ZapytaniePagination(LimitOffsetPagination):
    max_limit = MAKS_LIMIT


class ZapytanieAPIBaseViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Baza: wykonuje DjangoQL, mapuje błędy na 400. Podklasa ustawia
    ``model`` i ``serializer_class``."""

    permission_classes = [MoznaUzywacZapytania]
    pagination_class = _ZapytaniePagination
    model = None

    def _q(self):
        return (self.request.query_params.get("q") or "").strip()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["contenttype_to_viewname"] = {
            ContentType.objects.get_for_model(m).pk: v
            for m, v in MODELE_DETAIL_VIEWNAME.items()
        }
        return context

    def _uczelnia(self):
        """Uczelnia oglądającego (z mapowania Site→Uczelnia requestu)."""
        return Uczelnia.objects.get_for_request(self.request)

    def _scope_queryset(self, qs):
        """Zawężenie do polityki widoczności API. Domyślnie no-op; podklasa
        nadpisuje per model. NIE pomijaj — to izolacja multi-uczelnia."""
        return qs

    def get_queryset(self):
        q = self._q()
        qs = self.model.objects.all()
        if not q:
            return qs.none()
        # Izolacja/widoczność MUSI zadziałać przed apply_search — inaczej
        # DjangoQL widzi rekordy spoza uczelni oglądającego (uwaga #1).
        qs = self._scope_queryset(qs)
        # apply_search jest leniwe — DjangoQLError poleci dopiero na parsie
        # (tu), FieldError/ValidationError przy ewaluacji (w list()).
        return apply_search(qs, q, schema=RekordLLMSchema).distinct()

    def list(self, request, *args, **kwargs):
        try:
            with statement_timeout(ZAPYTANIE_TIMEOUT_MS):
                return super().list(request, *args, **kwargs)
        except (DjangoQLError, FieldError, ValidationError, ValueError) as exc:
            return Response(error_payload(exc, self._q()), status=400)
        except OperationalError:
            return Response(
                {"error": "Zapytanie trwało za długo — zawęź warunki."},
                status=503,
            )


class ZapytanieRekordViewSet(ZapytanieAPIBaseViewSet):
    model = Rekord
    serializer_class = SzukajSerializer

    def _scope_queryset(self, qs):
        # Ta sama polityka co /api/v1/szukaj/ (wspólny helper).
        return scope_rekord_api(qs, self._uczelnia(), MODELE_DETAIL_VIEWNAME)


class ZapytanieAutorViewSet(ZapytanieAPIBaseViewSet):
    model = Autor
    serializer_class = AutorKompaktSerializer

    def _scope_queryset(self, qs):
        return scope_autor_do_uczelni(qs, self._uczelnia())

    def get_queryset(self):
        # tnie N+1: AutorKompaktSerializer czyta tytul/aktualna_jednostka
        # (oba nullable → LEFT JOIN, bez ryzyka wycięcia wierszy)
        return super().get_queryset().select_related("tytul", "aktualna_jednostka")


class ZapytanieAutorzyViewSet(ZapytanieAPIBaseViewSet):
    model = Autorzy
    serializer_class = AutorzyKompaktSerializer

    def _scope_queryset(self, qs):
        return scope_autorzy_do_uczelni(qs, self._uczelnia())

    def get_queryset(self):
        # select_related ucina N+1 z kompaktowego serializera dla FK-i,
        # które są zawsze wypełnione (rekord/autor/jednostka/
        # typ_odpowiedzialnosci). ``dyscyplina_naukowa`` bywa NULL (autor
        # bez przypisanej dyscypliny na dany rok), a pole modelu nie ma
        # ``null=True`` — Django wygenerowałoby dla niego INNER JOIN i po
        # cichu zgubiłoby takie wiersze wyniku (zweryfikowane: 0 wierszy
        # zamiast 1 przy select_related, poprawnie przy prefetch_related).
        # Dlatego dyscyplina_naukowa idzie osobnym, zbiorczym prefetchem.
        return (
            super()
            .get_queryset()
            .select_related("rekord", "autor", "jednostka", "typ_odpowiedzialnosci")
            .prefetch_related("dyscyplina_naukowa")
            # Autorzy to managed=False mat-view bez Meta.ordering — bez
            # jawnego porządku LimitOffsetPagination na Postgresie może
            # gubić/dublować wiersze między stronami (kolejność bez
            # ORDER BY nie jest gwarantowana). ``rekord_id`` jest kolumną
            # array (TupleField), ale Postgres porównuje tablice
            # leksykograficznie, więc sortowanie po niej działa.
            .order_by("rekord_id", "kolejnosc", "autor_id")
        )

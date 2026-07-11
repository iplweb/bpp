"""Autoryzowane wyszukiwanie DjangoQL po API — ``GET /api/v1/zapytanie/<model>/``.

Wystawia istniejący silnik ``apply_search`` (schemat ``RekordLLMSchema``) w
warstwie DRF, read-only, gate'owane ``MoznaUzywacZapytania``. Kształt wyników:
kompaktowa płaska projekcja per model.
"""

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldError, ValidationError
from djangoql.exceptions import DjangoQLError
from djangoql.queryset import apply_search
from rest_framework import mixins, viewsets
from rest_framework.response import Response

from api_v1.permissions import MoznaUzywacZapytania
from api_v1.serializers.szukaj import SzukajSerializer
from api_v1.serializers.zapytanie import (
    AutorKompaktSerializer,
    AutorzyKompaktSerializer,
)
from api_v1.viewsets.szukaj import MODELE_DETAIL_VIEWNAME
from bpp.djangoql_errors import error_payload
from bpp.djangoql_schema import RekordLLMSchema
from bpp.models import Autor
from bpp.models.cache import Autorzy, Rekord

#: Twardy cap paginacji — jedno żądanie nie ciągnie całej bazy.
MAKS_LIMIT = 100


class ZapytanieAPIBaseViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Baza: wykonuje DjangoQL, mapuje błędy na 400. Podklasa ustawia
    ``model`` i ``serializer_class``."""

    permission_classes = [MoznaUzywacZapytania]
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

    def get_queryset(self):
        q = self._q()
        qs = self.model.objects.all()
        if not q:
            return qs.none()
        # apply_search jest leniwe — DjangoQLError poleci dopiero na parsie
        # (tu), FieldError/ValidationError przy ewaluacji (w list()).
        return apply_search(qs, q, schema=RekordLLMSchema).distinct()

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except (DjangoQLError, FieldError, ValidationError, ValueError) as exc:
            return Response(error_payload(exc, self._q()), status=400)


class ZapytanieRekordViewSet(ZapytanieAPIBaseViewSet):
    model = Rekord
    serializer_class = SzukajSerializer


class ZapytanieAutorViewSet(ZapytanieAPIBaseViewSet):
    model = Autor
    serializer_class = AutorKompaktSerializer

    def get_queryset(self):
        # tnie N+1: AutorKompaktSerializer czyta tytul/aktualna_jednostka
        # (oba nullable → LEFT JOIN, bez ryzyka wycięcia wierszy)
        return super().get_queryset().select_related("tytul", "aktualna_jednostka")


class ZapytanieAutorzyViewSet(ZapytanieAPIBaseViewSet):
    model = Autorzy
    serializer_class = AutorzyKompaktSerializer

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
        )

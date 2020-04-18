import django_filters
from rest_framework import viewsets

from api_v1.serializers.wydawnictwo_zwarte import (
    Wydawnictwo_Zwarte_AutorSerializer,
    Wydawnictwo_ZwarteSerializer,
)

from bpp.models import Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor


class Wydawnictwo_Zwarte_AutorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Wydawnictwo_Zwarte_Autor.objects.all()
    serializer_class = Wydawnictwo_Zwarte_AutorSerializer


class Wydawnictwo_ZwarteFilterSet(django_filters.rest_framework.FilterSet):
    ostatnio_zmieniony = django_filters.DateTimeFromToRangeFilter("ostatnio_zmieniony")

    class Meta:
        fields = ["ostatnio_zmieniony", "charakter_formalny"]
        model = Wydawnictwo_Zwarte


class Wydawnictwo_ZwarteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Wydawnictwo_Zwarte.objects.all()
    serializer_class = Wydawnictwo_ZwarteSerializer
    filterset_class = Wydawnictwo_ZwarteFilterSet

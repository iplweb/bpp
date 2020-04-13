import django_filters
from rest_framework import viewsets

from api_v1.serializers.zrodlo import Rodzaj_ZrodlaSerializer, ZrodloSerializer

from bpp.models import Rodzaj_Zrodla, Zrodlo


class ZrodloFilterSet(django_filters.rest_framework.FilterSet):
    ostatnio_zmieniony = django_filters.DateTimeFromToRangeFilter("ostatnio_zmieniony")

    class Meta:
        fields = ["ostatnio_zmieniony"]
        model = Zrodlo


class ZrodloViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Zrodlo.objects.all()
    serializer_class = ZrodloSerializer
    filterset_class = ZrodloFilterSet


class Rodzaj_ZrodlaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Rodzaj_Zrodla.objects.all()
    serializer_class = Rodzaj_ZrodlaSerializer
